"""
Custom exceptions for PingCrafty v0.2
"""

class PingCraftyError(Exception):
    """Base exception for PingCrafty"""
    pass

class ScannerError(PingCraftyError):
    """Scanner-related errors"""
    pass

class ProtocolError(PingCraftyError):
    """Protocol-related errors"""
    pass

class DatabaseError(PingCraftyError):
    """Database-related errors"""
    pass

class ConfigError(PingCraftyError):
    """Configuration-related errors"""
    pass

class BlacklistError(PingCraftyError):
    """Blacklist-related errors"""
    pass

class GeolocationError(PingCraftyError):
    """Geolocation-related errors"""
    pass

class WebhookError(PingCraftyError):
    """Webhook-related errors"""
    pass

class MemoryError(PingCraftyError):
    """Memory management errors"""
    pass

class ConcurrencyError(PingCraftyError):
    """Concurrency-related errors"""
    pass

class DiscoveryError(PingCraftyError):
    """Discovery-related errors"""
    pass

class ParsingError(PingCraftyError):
    """Parsing-related errors"""
    pass 