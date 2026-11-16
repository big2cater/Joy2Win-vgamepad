# -*- coding: utf-8 -*-
"""HD Rumble output stream for Joy-Con 2 over BLE.

One task per (pair, side) sends a fresh 12 ms packet while either XInput motor
is on, then sends a zero-amplitude packet and stops. Frames are generated
from the *current* motor state on every tick, so a slow GATT write simply
delays the next packet instead of stacking stale packets in the queue
(latest-value-wins, as used by NS2Pro-Bridge-Windows).

All public async methods run on the application's BLE event loop. The
vgamepad vibration callback reaches them through run_coroutine_threadsafe
in duo_joycon.py / single_joycon.py.
"""

import asyncio
import time

from controller_command import UUID_CMD
from controllers.hd_rumble import (
    AMPLITUDE_DEFAULT,
    LEGACY_EFFECT_OFF,
    LEGACY_EFFECT_ON,
    RUMBLE_IDLE_TIMEOUT,
    RUMBLE_INTERVAL,
    RUMBLE_PACKET_LENGTH,
    build_frame,
    get_rumble_uuid,
)
from logger_config import debug, info, warning

FALLBACK_AFTER_FAILURES = 3
LEGACY_POLL_INTERVAL = 0.1
MOTOR_DEADZONE = 5
MOTOR_MAX = 255

# A single GATT write must never be wrapped in asyncio.wait_for(): cancelling
# a WinRT write leaves the operation running, and its completion callback then
# calls set_result on a cancelled future ("InvalidStateError: invalid state")
# while the packet itself is dropped. Slow links are handled by the adaptive
# cadence below instead.
SLOW_WRITE_WARN = 1.0

# A dropped stop packet means a Joy-Con keeps buzzing, so retry it a few times
# before giving up on the stream.
STOP_ATTEMPTS = 3
STOP_RETRY_INTERVAL = 0.05

# The stop packet is sent write-without-response, which is fire-and-forget: a
# single lost packet leaves the actuator running until the controller's own
# watchdog fires. Repeats must be spaced out, not packed: sending them every
# 12 ms just keeps filling the same Windows BLE queue that delayed the first
# one. Four packets 40 ms apart cover ~160 ms of latency without competing
# with each other.
STOP_REPEAT = 4
STOP_REPEAT_INTERVAL = 0.040

# Cadence diagnostics. If fps stays far below 1/interval, or the write time
# approaches the interval, the BLE path cannot keep up and the stop packet is
# queued behind stale frames -- which is what "log says off but it still
# buzzes" looks like. Printed once per interval while rumble is active.
STATS_INTERVAL = 2.0

# Upper bound for the adaptive cadence when even the 30 ms base period cannot
# be met (very congested links). Rumble still holds its state between packets.
SLOW_INTERVAL = 0.050


def _clamp_intensity(value):
    try:
        return max(0, min(MOTOR_MAX, int(value)))
    except (TypeError, ValueError):
        return 0


def _resolve_write_mode(client, uuid):
    """Return True when the characteristic needs an acknowledged write.

    Decided from the GATT properties rather than by trying and catching: an
    exception-driven fallback would re-send the packet on *every* transient
    error, doubling traffic on a link that is already struggling.
    """
    try:
        characteristic = client.services.get_characteristic(uuid)
        properties = list(characteristic.properties or [])
    except Exception:
        # No service table (or not a real client): assume the documented
        # write-without-response behaviour.
        return False
    if "write-without-response" in properties:
        return False
    return "write" in properties


class _StreamState:
    def __init__(self, client, side, pair_id=0):
        self.client = client
        self.side = side
        self.pair_id = pair_id
        self.uuid = get_rumble_uuid(side)
        self.large = 0
        self.small = 0
        self.counter = 0
        self.last_update = time.monotonic()
        self.failures = 0
        self.legacy = False
        self.legacy_active = False
        self.stopped = False
        # The rumble characteristics are write-without-response. Writing with
        # response makes every packet wait for an ATT acknowledgement, which
        # cannot sustain a 12 ms cadence -- the queue backs up and the final
        # zero-amplitude packet never leaves.
        self.write_response = _resolve_write_mode(client, self.uuid)
        self.announced = False
        self.stop_attempts = 0
        self.frames = 0
        self.write_total = 0.0
        self.write_max = 0.0
        self.last_stats = time.monotonic()
        # Per-burst totals: a game can buzz for 100 ms, which says nothing in a
        # fixed 2 s window but everything when reported as one line at "off".
        self.burst_started = 0.0
        self.burst_frames = 0
        self.burst_write_total = 0.0


class RumbleStream:
    def __init__(self, interval=RUMBLE_INTERVAL,
                 idle_timeout=RUMBLE_IDLE_TIMEOUT,
                 ceiling=AMPLITUDE_DEFAULT, strength=100):
        self._interval = max(0.004, float(interval))
        self._idle_timeout = max(0.1, float(idle_timeout))
        self._ceiling = ceiling
        self._strength = max(0, min(100, int(strength)))
        self._states = {}
        self._tasks = {}
        self._closed = False

    def set_strength(self, percent):
        self._strength = max(0, min(100, int(percent)))

    def set_ceiling(self, ceiling):
        self._ceiling = max(0, min(0x3FF, int(ceiling)))

    @staticmethod
    def _key(pair_id, side):
        return (int(pair_id), side)

    async def update(self, pair_id, side, client, large_motor, small_motor):
        """Apply one XInput rumble update (two motor channels, 0..255)."""
        if self._closed:
            return
        key = self._key(pair_id, side)
        state = self._states.get(key)
        if state is None:
            state = _StreamState(client, side, pair_id)
            self._states[key] = state
        else:
            if state.client is not client:
                # A different client means the controller reconnected. Retry
                # the HD path instead of inheriting the previous session's
                # fallback and failure counters.
                state.failures = 0
                state.legacy = False
                state.legacy_active = False
            state.client = client
            state.uuid = get_rumble_uuid(side)
            state.write_response = _resolve_write_mode(client, state.uuid)

        large = _clamp_intensity(large_motor)
        small = _clamp_intensity(small_motor)
        if large < MOTOR_DEADZONE:
            large = 0
        if small < MOTOR_DEADZONE:
            small = 0
        active = bool(large or small)
        state.large = large
        state.small = small
        state.last_update = time.monotonic()

        if active:
            state.stopped = False
            state.stop_attempts = 0
            if not state.announced:
                # One line per rumble burst keeps the console readable while
                # still proving that updates actually reach the controller.
                state.announced = True
                state.burst_started = time.monotonic()
                state.burst_frames = 0
                state.burst_write_total = 0.0
                info(f"[RUMBLE] pair={pair_id} {side}: rumble on "
                     f"(large={large}, small={small})")
        elif state.stopped:
            # Games often keep sending (0, 0) every frame. The zero-amplitude
            # stop packet has already been sent, so do not restart the task.
            return

        task = self._tasks.get(key)
        if task is None or task.done():
            self._tasks[key] = asyncio.create_task(self._run(key))

    def update_sync(self, pair_id, side, client, large_motor, small_motor):
        """Thread-safe fast path for an already-running stream.

        The vgamepad vibration callback fires on its own thread, dozens of
        times a second while a game rumbles. Hopping into the event loop for
        each one (run_coroutine_threadsafe) costs a loop wakeup per call, and
        enough of them starve the 12 ms sender -- measured cadence collapsed
        to ~12 fps with a 0.7 ms write time, i.e. the time was spent scheduling,
        not writing. Updating two ints is atomic under the GIL, so the steady
        state needs no loop involvement at all.

        Returns False when there is no live task for this side; the caller then
        uses the async path, which is the only place that may create one.
        """
        key = self._key(pair_id, side)
        task = self._tasks.get(key)
        if task is None or task.done():
            return False
        state = self._states.get(key)
        if state is None:
            return False

        large = _clamp_intensity(large_motor)
        small = _clamp_intensity(small_motor)
        if large < MOTOR_DEADZONE:
            large = 0
        if small < MOTOR_DEADZONE:
            small = 0
        state.client = client
        state.large = large
        state.small = small
        state.last_update = time.monotonic()
        if large or small:
            state.stopped = False
            state.stop_attempts = 0
            if not state.announced:
                state.announced = True
                state.burst_started = time.monotonic()
                state.burst_frames = 0
                state.burst_write_total = 0.0
                info(f"[RUMBLE] pair={pair_id} {side}: rumble on "
                     f"(large={large}, small={small})")
        return True

    def stop_sync(self, pair_id, side):
        """Cancel a stream from a synchronous cleanup path on the same loop."""
        key = self._key(pair_id, side)
        task = self._tasks.pop(key, None)
        if task is not None:
            task.cancel()
        self._states.pop(key, None)

    async def stop(self, pair_id, side):
        key = self._key(pair_id, side)
        state = self._states.get(key)
        if state is not None:
            await self._send_stop(state)
        self.stop_sync(pair_id, side)

    async def silence_all(self):
        """Force every stream quiet right now, cancelling pending sends.

        Used by the tray menu as an escape hatch, and as a diagnostic: if this
        does not stop the buzzing, the stop packet never reaches the controller.
        """
        for key in list(self._states):
            state = self._states.get(key)
            if state is None:
                continue
            # Clear the requested intensity first: _send_stop returns early if
            # a non-zero value arrives while it is silencing.
            state.large = 0
            state.small = 0
            task = self._tasks.pop(key, None)
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            try:
                await self._send_stop(state)
            except Exception as exc:
                debug(f"[RUMBLE] silence failed for {key}: {exc}")

    async def shutdown(self):
        """Send stop packets, then cancel every stream task."""
        self._closed = True
        for state in list(self._states.values()):
            # Retry: a dropped stop packet here means the controller keeps
            # buzzing after the app has exited.
            for attempt in range(STOP_ATTEMPTS):
                try:
                    if await self._send_stop(state):
                        break
                except Exception as exc:
                    debug(f"[RUMBLE] shutdown stop failed: {exc}")
                if attempt < STOP_ATTEMPTS - 1:
                    await asyncio.sleep(STOP_RETRY_INTERVAL)
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._states.clear()

    @staticmethod
    def _pad(client, frame):
        """Pad a rumble packet to the length real implementations send.

        Only when the negotiated MTU has room for the full 42-byte packet.
        Otherwise send the frame exactly as encoded: a half-padded 20-byte
        variant is a length this project has never seen work on hardware.
        """
        mtu = getattr(client, "mtu_size", 0) or 0
        if mtu < RUMBLE_PACKET_LENGTH + 3:
            return frame
        return frame + bytes(RUMBLE_PACKET_LENGTH - len(frame))

    async def _write(self, state, frame, uuid=None, force_response=None):
        client = state.client
        if client is None or not getattr(client, "is_connected", False):
            return False
        char = uuid or state.uuid
        if uuid is None:
            # Only rumble packets are padded; command writes to UUID_CMD must
            # keep their exact length or the firmware rejects them.
            frame = self._pad(client, frame)
        mode = state.write_response if force_response is None else force_response
        try:
            # Do NOT wrap this in asyncio.wait_for. Cancelling a WinRT GATT
            # write leaves the underlying operation running; when it completes
            # it calls set_result on the already-cancelled future and raises
            # "InvalidStateError: invalid state" from the event loop -- and,
            # worse, the packet itself is dropped. A timed-out stop packet is
            # exactly why a Joy-Con kept buzzing after "rumble off".
            await client.write_gatt_char(char, frame, response=mode)
            return True
        except Exception as exc:
            debug(f"[RUMBLE] write failed: {type(exc).__name__}: {exc}")
            return False

    async def _send_stop(self, state):
        if state.legacy:
            # Stored-effect commands go to the command characteristic, which
            # does expect an acknowledged write.
            ok = await self._write(state, LEGACY_EFFECT_OFF, UUID_CMD,
                                   force_response=True)
            state.legacy_active = False
        else:
            ok = False
            for index in range(STOP_REPEAT):
                if state.large or state.small:
                    # A new rumble request arrived while silencing. Hand
                    # control back to the stream instead of finishing the
                    # burst, otherwise rapid start/stop games feel laggy.
                    state.announced = False
                    return True
                # Zero amplitude, carriers unchanged: this is the stop packet
                # joy2con sends to a Joy-Con 2 (0x187 / 0x112, amplitude 0).
                frame = build_frame(state.counter, 0, 0,
                                    ceiling=self._ceiling,
                                    strength=self._strength)
                state.counter = (state.counter + 1) & 0x0F
                # Ask for an acknowledgement on the first packet when the
                # characteristic permits it; a single confirmed zero packet is
                # what actually stops the actuator, the rest are cheap repeats
                # that cover a lost first attempt.
                force = True if index == 0 else None
                # shield: if this burst is cancelled mid-way, the packet
                # already in flight still reaches the controller instead of
                # being dropped with an InvalidStateError.
                if await asyncio.shield(
                    self._write(state, frame, force_response=force)
                ):
                    ok = True
                if index < STOP_REPEAT - 1:
                    if not getattr(state.client, "is_connected", False):
                        break
                    await asyncio.sleep(STOP_REPEAT_INTERVAL)
        if state.announced:
            state.announced = False
            elapsed_ms = (time.monotonic() - state.burst_started) * 1000 \
                if state.burst_started else 0.0
            avg_ms = (state.burst_write_total / state.burst_frames * 1000) \
                if state.burst_frames else 0.0
            detail = (f"{state.burst_frames} frames in {elapsed_ms:.0f} ms, "
                      f"avg write {avg_ms:.1f} ms")
            if ok:
                info(f"[RUMBLE] pair={state.pair_id} {state.side}: "
                     f"rumble off ({detail})")
            else:
                warning(f"[RUMBLE] pair={state.pair_id} {state.side}: "
                        f"stop packet not delivered ({detail})")
        # Only claim the actuator is quiet once the zero-amplitude packet
        # actually made it out. Claiming it after a failed write is what left
        # a Joy-Con buzzing: the stream considered itself stopped and never
        # retried.
        state.stopped = ok
        return ok

    async def _run(self, key):
        # Absolute schedule: sleep(interval) after each write would add the
        # write duration to every period, so the cadence drifts slower and
        # slower and the pad hears gaps. Schedule against a monotonic target
        # instead, the way a fixed-rate timer does.
        next_tick = time.monotonic()
        interval = self._interval
        slow_streak = 0
        try:
            while not self._closed:
                state = self._states.get(key)
                if state is None:
                    return
                active = bool(state.large or state.small)
                idle = time.monotonic() - state.last_update > self._idle_timeout
                if not active or idle:
                    if await self._send_stop(state):
                        return
                    state.stop_attempts += 1
                    if state.stop_attempts >= STOP_ATTEMPTS:
                        warning(
                            f"[RUMBLE] pair={key[0]} {key[1]}: gave up sending "
                            f"the stop packet after {STOP_ATTEMPTS} attempts"
                        )
                        return
                    await asyncio.sleep(STOP_RETRY_INTERVAL)
                    continue

                if state.legacy:
                    # Stored effects are one-shot ~1 s samples. Only write on
                    # an edge; polling at 12 ms would restart the sample.
                    if not state.legacy_active:
                        # Only mark the sample as playing once the write has
                        # actually landed. Setting the flag unconditionally
                        # meant a single transient GATT error silenced rumble
                        # until the next stop packet. Retrying here is cheap:
                        # this branch already throttles at LEGACY_POLL_INTERVAL.
                        if await self._write(state, LEGACY_EFFECT_ON, UUID_CMD):
                            state.legacy_active = True
                    await asyncio.sleep(LEGACY_POLL_INTERVAL)
                    continue

                frame = build_frame(state.counter, state.large, state.small,
                                    ceiling=self._ceiling, strength=self._strength)
                state.counter = (state.counter + 1) & 0x0F
                write_start = time.monotonic()
                # shield so a cancellation of this task cannot abort the write
                # that is already in flight (which would drop the packet and
                # raise InvalidStateError from the WinRT completion callback).
                ok = await asyncio.shield(self._write(state, frame))
                write_elapsed = time.monotonic() - write_start
                state.frames += 1
                state.write_total += write_elapsed
                state.burst_frames += 1
                state.burst_write_total += write_elapsed
                if write_elapsed > state.write_max:
                    state.write_max = write_elapsed
                now = time.monotonic()
                stats_window = now - state.last_stats
                # Only report sustained bursts; a 100 ms buzz would otherwise
                # print a meaningless "0 fps".
                if stats_window >= STATS_INTERVAL and state.frames >= 5:
                    fps = state.frames / stats_window
                    avg_ms = state.write_total / state.frames * 1000
                    info(f"[RUMBLE] pair={state.pair_id} {state.side}: "
                         f"{fps:.0f} fps, write avg {avg_ms:.1f} ms, "
                         f"max {state.write_max * 1000:.1f} ms")
                    state.frames = 0
                    state.write_total = 0.0
                    state.write_max = 0.0
                    state.last_stats = now
                if ok:
                    state.failures = 0
                else:
                    state.failures += 1
                    if state.failures >= FALLBACK_AFTER_FAILURES:
                        state.legacy = True
                        state.legacy_active = False
                        warning(
                            f"[RUMBLE] pair={key[0]} side={key[1]}: HD rumble "
                            f"characteristic unavailable, using stored effect"
                        )
                # If a write takes about as long as the whole period, the link
                # cannot sustain the cadence and every extra packet just piles
                # up in the driver queue. Relax instead of queueing.
                if write_elapsed > interval * 0.9:
                    slow_streak += 1
                    if slow_streak >= 5 and interval < SLOW_INTERVAL:
                        interval = min(SLOW_INTERVAL, interval * 2)
                        slow_streak = 0
                        info(
                            f"[RUMBLE] pair={state.pair_id} {state.side}: BLE "
                            f"cannot keep up ({write_elapsed * 1000:.0f} ms per "
                            f"write), cadence relaxed to {interval * 1000:.0f} ms"
                        )
                else:
                    slow_streak = 0
                next_tick += interval
                delay = next_tick - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                else:
                    # Fell behind (slow GATT write): resync instead of bursting
                    # to catch up, which would only deepen the backlog.
                    next_tick = time.monotonic()
        except asyncio.CancelledError:
            # A cancelled stream must still silence the actuator: disconnect
            # and shutdown cancel these tasks while rumble is running.
            state = self._states.get(key)
            if state is not None:
                try:
                    await asyncio.shield(self._send_stop(state))
                except Exception as exc:
                    debug(f"[RUMBLE] stop after cancel failed: {exc}")
            raise
        except Exception as exc:
            debug(f"[RUMBLE] stream stopped: {type(exc).__name__}: {exc}")
        finally:
            if self._tasks.get(key) is asyncio.current_task():
                self._tasks.pop(key, None)


_rumble_stream = None


def get_rumble_stream():
    global _rumble_stream
    if _rumble_stream is None:
        try:
            from config import Config
            strength = getattr(Config(), "rumble_strength", 100)
        except Exception:
            strength = 100
        _rumble_stream = RumbleStream(strength=strength)
    return _rumble_stream
