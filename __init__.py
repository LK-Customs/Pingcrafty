"""
PingCrafty v0.2 - Modular Minecraft Server Scanner

A high-performance, modular Minecraft server scanner with advanced features
including real-time UI, database storage, geolocation, and comprehensive
server information extraction.
"""

__version__ = "0.2.0"
__author__ = "PingCrafty Team"
__license__ = "MIT"
__description__ = "Modular Minecraft Server Scanner"

# Core imports for easy access
from .core.scanner import MinecraftScanner, ScanResult, ScanStats
from .core.config import ConfigManager
from .core.exceptions import PingCraftyError

# Version info
VERSION_INFO = {
    'version': __version__,
    'author': __author__,
    'license': __license__,
    'description': __description__
}

def get_version():
    """Get version string"""
    return __version__

def get_version_info():
    """Get detailed version information"""
    return VERSION_INFO.copy()

# Main exports
__all__ = [
    'MinecraftScanner',
    'ScanResult', 
    'ScanStats',
    'ConfigManager',
    'PingCraftyError',
    'get_version',
    'get_version_info',
    '__version__'
] 