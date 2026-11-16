"""Test package for Joy2Win-vgamepad.

An explicit ``__init__.py`` is required here. Without it this directory is only
an implicit namespace package, which loses to a *regular* ``tests`` package
installed into site-packages by some third-party distributions. When that
happens ``python -m unittest tests.test_core`` resolves ``tests`` to the
unrelated site-packages package and fails with::

    ModuleNotFoundError: No module named 'tests.test_core'

Making this a regular package keeps ``sys.path[0]`` (the project root) winning
regardless of what is installed globally.
"""
