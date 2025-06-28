"""
Configuration management with YAML and validation
"""

import yaml
import logging
from typing import Dict, Any
from pathlib import Path

from .exceptions import ConfigError
from .config_types import (
    DatabaseConfig, ScannerConfig, DiscoveryConfig,
    ConcurrencyConfig, MemoryConfig, BlacklistConfig,
    GeolocationConfig, WebhookConfig, LoggingConfig, UIConfig
)

logger = logging.getLogger(__name__)

class ConfigManager:
    """Configuration manager with validation and defaults"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.raw_config = self._load_config()
        
        # Parse configuration sections
        self.database = self._parse_database_config()
        self.scanner = self._parse_scanner_config()
        self.discovery = self._parse_discovery_config()
        self.concurrency = self._parse_concurrency_config()
        self.memory = self._parse_memory_config()
        self.blacklist = self._parse_blacklist_config()
        self.geolocation = self._parse_geolocation_config()
        self.webhook = self._parse_webhook_config()
        self.logging = self._parse_logging_config()
        self.ui = self._parse_ui_config()
        
        self._validate_config()
        logger.info(f"Configuration loaded from {config_path}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            logger.warning(f"Config file {self.config_path} not found, creating default")
            self._create_default_config()
        
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigError(f"Failed to load config: {e}")
    
    def _create_default_config(self) -> None:
        """Create default configuration file"""
        default_config = {
            'database': vars(DatabaseConfig()),
            'scanner': vars(ScannerConfig()),
            'discovery': vars(DiscoveryConfig()),
            'concurrency': vars(ConcurrencyConfig()),
            'memory': vars(MemoryConfig()),
            'blacklist': vars(BlacklistConfig()),
            'geolocation': vars(GeolocationConfig()),
            'webhook': vars(WebhookConfig()),
            'logging': vars(LoggingConfig()),
            'ui': vars(UIConfig())
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)
    
    def _parse_database_config(self) -> DatabaseConfig:
        """Parse database configuration"""
        db_config = self.raw_config.get('database', {})
        return DatabaseConfig(**db_config)
    
    def _parse_scanner_config(self) -> ScannerConfig:
        """Parse scanner configuration"""
        scanner_config = self.raw_config.get('scanner', {})
        return ScannerConfig(**scanner_config)
    
    def _parse_discovery_config(self) -> DiscoveryConfig:
        """Parse discovery configuration"""
        discovery_config = self.raw_config.get('discovery', {})
        return DiscoveryConfig(**discovery_config)
    
    def _parse_concurrency_config(self) -> ConcurrencyConfig:
        """Parse concurrency configuration"""
        concurrency_config = self.raw_config.get('concurrency', {})
        return ConcurrencyConfig(**concurrency_config)
    
    def _parse_memory_config(self) -> MemoryConfig:
        """Parse memory configuration"""
        memory_config = self.raw_config.get('memory', {})
        return MemoryConfig(**memory_config)
    
    def _parse_blacklist_config(self) -> BlacklistConfig:
        """Parse blacklist configuration"""
        blacklist_config = self.raw_config.get('blacklist', {})
        return BlacklistConfig(**blacklist_config)
    
    def _parse_geolocation_config(self) -> GeolocationConfig:
        """Parse geolocation configuration"""
        geolocation_config = self.raw_config.get('geolocation', {})
        return GeolocationConfig(**geolocation_config)
    
    def _parse_webhook_config(self) -> WebhookConfig:
        """Parse webhook configuration"""
        webhook_config = self.raw_config.get('webhook', {})
        return WebhookConfig(**webhook_config)
    
    def _parse_logging_config(self) -> LoggingConfig:
        """Parse logging configuration"""
        logging_config = self.raw_config.get('logging', {})
        return LoggingConfig(**logging_config)
    
    def _parse_ui_config(self) -> UIConfig:
        """Parse UI configuration"""
        ui_config = self.raw_config.get('ui', {})
        return UIConfig(**ui_config)
    
    def _validate_config(self) -> None:
        """Validate configuration values"""
        # Validate database config
        if self.database.type not in ['sqlite', 'postgresql']:
            raise ConfigError(f"Invalid database type: {self.database.type}")
        
        # Validate scanner config
        if self.scanner.timeout <= 0:
            raise ConfigError("Scanner timeout must be positive")
        if self.scanner.rate_limit <= 0:
            raise ConfigError("Rate limit must be positive")
        
        # Validate discovery config
        if self.discovery.method not in ['range', 'masscan', 'file']:
            raise ConfigError(f"Invalid discovery method: {self.discovery.method}")
        if not self.discovery.ports:
            raise ConfigError("At least one port must be specified")
        
        # Validate concurrency config
        if self.concurrency.max_concurrent <= 0:
            raise ConfigError("Max concurrent connections must be positive")
        if self.concurrency.batch_size <= 0:
            raise ConfigError("Batch size must be positive")
        
        # Validate memory config
        if self.memory.max_memory_mb <= 0:
            raise ConfigError("Max memory must be positive")
        
        # Validate webhook config
        if self.webhook.enabled and not self.webhook.url:
            raise ConfigError("Webhook URL must be specified when enabled")
        
        logger.info("Configuration validation passed") 