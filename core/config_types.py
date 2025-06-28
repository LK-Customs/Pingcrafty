"""
Shared configuration types for PingCrafty
"""

from typing import List, Optional
from dataclasses import dataclass, field

@dataclass
class DatabaseConfig:
    type: str = "sqlite"
    path: str = "servers.db"
    host: str = "localhost"
    port: int = 5432
    database: str = "pingcrafty"
    user: str = "postgres"
    password: str = "password"
    pool_size: int = 10

@dataclass
class ScannerConfig:
    timeout: float = 5.0
    protocol_version: int = 770
    scan_all_protocols: bool = False
    protocol_versions: List[int] = field(default_factory=lambda: [
        770,  # 1.21
        767,  # 1.21
        766,  # 1.20.5-1.20.6
        765,  # 1.20.3-1.20.4
        764,  # 1.20.2
        763,  # 1.20-1.20.1
        762,  # 1.19.4
        761,  # 1.19.3
        760,  # 1.19.1-1.19.2
        759,  # 1.19
        758,  # 1.18.2
        757,  # 1.18-1.18.1
        754,  # 1.16.4-1.16.5
        47,   # 1.8.x
        5,    # 1.7.6-1.7.10
    ])
    retries: int = 2
    legacy_support: bool = True
    rate_limit: int = 1000

@dataclass
class DiscoveryConfig:
    method: str = "range"  # range, masscan, file
    ports: List[int] = field(default_factory=lambda: [25565])
    batch_size: int = 1000
    masscan_rate: int = 10000
    masscan_excludes: str = "exclude.conf"

@dataclass
class ConcurrencyConfig:
    max_concurrent: int = 1000
    batch_size: int = 100
    max_connections_per_host: int = 10

@dataclass
class MemoryConfig:
    max_memory_mb: int = 1000
    gc_interval: int = 1000
    enable_monitoring: bool = True

@dataclass
class BlacklistConfig:
    enabled: bool = True
    auto_update: bool = True
    file_path: str = "blacklist.txt"

@dataclass
class GeolocationConfig:
    enabled: bool = True
    provider: str = "geoip2"
    database_path: str = "GeoLite2-City.mmdb"
    cache_duration: int = 86400

@dataclass
class WebhookConfig:
    enabled: bool = False
    url: str = ""
    batch_size: int = 50
    include_stats: bool = True

@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "pingcrafty.log"
    max_size_mb: int = 100
    backup_count: int = 5

@dataclass
class UIConfig:
    enabled: bool = True
    refresh_rate: int = 4
    show_details: bool = True 