"""
Error handling utilities for Joy2Win-vgamepad
"""
import os
import configparser
from logger_config import info, warning, error

def validate_config_file(config_path='config.ini'):
    """
    Validate and repair config file if corrupted
    
    Args:
        config_path: Path to config file
    
    Returns:
        bool: True if config is valid or repaired
    """
    default_config = """[Controller]
controller = 0
orientation = 0
led_player = 1
save_mac_address = 0
enable_dsu = 1
mouse_mode = 0
sll_mapping = XUSB_GAMEPAD_RIGHT_SHOULDER
srl_mapping = 
slr_mapping = XUSB_GAMEPAD_X
srr_mapping = 

[Bluetooth]
mac_address = 

[Pair_0]
sll_mapping = 
srl_mapping = 
slr_mapping = 
srr_mapping = 

[Pair_1]
sll_mapping = 
srl_mapping = 
slr_mapping = 
srr_mapping = 

[Pair_2]
sll_mapping = 
srl_mapping = 
slr_mapping = 
srr_mapping = 

[Pair_3]
sll_mapping = 
srl_mapping = 
slr_mapping = 
srr_mapping = 
"""
    
    try:
        # Check if file exists
        if not os.path.exists(config_path):
            warning(f"Config file {config_path} not found, creating default config")
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(default_config)
            info(f"Created default config file at {config_path}")
            return True
        
        # Try to parse the config
        parser = configparser.ConfigParser()
        parser.read(config_path, encoding='utf-8')
        
        # Check if essential sections exist
        required_sections = ['Controller']
        missing_sections = []
        
        for section in required_sections:
            if section not in parser.sections():
                missing_sections.append(section)
        
        if missing_sections:
            warning(f"Config file missing sections: {missing_sections}, repairing...")
            
            # Backup corrupted config
            backup_path = config_path + '.backup'
            try:
                os.rename(config_path, backup_path)
                info(f"Backed up corrupted config to {backup_path}")
            except Exception as e:
                error(f"Failed to backup config: {e}")
            
            # Create new default config
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(default_config)
            info(f"Created new default config file")
            return True
        
        info("Config file validated successfully")
        return True
        
    except Exception as e:
        error(f"Error validating config file: {e}")
        # Try to create default config as last resort
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(default_config)
            info(f"Created default config file after error")
            return True
        except Exception as e2:
            error(f"Failed to create default config: {e2}")
            return False


async def connect_with_retry(connect_func, max_retries=3, retry_delay=2):
    """
    Connect with automatic retry mechanism
    
    Args:
        connect_func: Async function to connect
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    
    Returns:
        Result of connect_func or None if all retries failed
    """
    import asyncio
    
    for attempt in range(1, max_retries + 1):
        try:
            info(f"Connection attempt {attempt}/{max_retries}")
            result = await connect_func()
            if result:
                info(f"Connection successful on attempt {attempt}")
                return result
        except Exception as e:
            error(f"Connection attempt {attempt} failed: {e}")
            
            if attempt < max_retries:
                warning(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                error(f"All {max_retries} connection attempts failed")
    
    return None


def handle_dsu_server_error(error_msg):
    """
    Handle DSU server errors gracefully
    
    Args:
        error_msg: Error message from DSU server
    
    Returns:
        str: User-friendly error message
    """
    error_patterns = {
        "Address already in use": "DSU 服务器端口已被占用，可能另一个实例正在运行",
        "Permission denied": "权限不足，无法启动 DSU 服务器",
        "Network is unreachable": "网络不可达，请检查网络连接",
    }
    
    for pattern, user_msg in error_patterns.items():
        if pattern in error_msg:
            error(f"DSU server error: {error_msg}")
            return user_msg
    
    error(f"DSU server error: {error_msg}")
    return f"DSU 服务器错误: {error_msg}"
