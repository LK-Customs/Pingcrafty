#!/usr/bin/env python3
"""
PingCrafty v0.2 - Modular Minecraft Server Scanner
Core scanner engine with pluggable architecture
"""

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any, Union, cast
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod

from core.config_types import (
    DatabaseConfig, ScannerConfig, DiscoveryConfig,
    ConcurrencyConfig, MemoryConfig, BlacklistConfig,
    GeolocationConfig, WebhookConfig
)
from core.database import DatabaseManager
from core.protocol import MinecraftProtocol, ProtocolConfig
from core.config import ConfigManager
from core.exceptions import ScannerError, ProtocolError

# Import module-specific config types
from utils.concurrency import ConcurrencyConfig as ModuleConcurrencyConfig
from utils.memory import MemoryConfig as ModuleMemoryConfig
from parsers.server_parser import ParsedServer

logger = logging.getLogger(__name__)

@dataclass
class ScanResult:
    """Container for scan results"""
    ip: str
    port: int
    success: bool
    server_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency: Optional[float] = None
    
    @classmethod
    def from_parsed_server(cls, parsed: ParsedServer, latency: Optional[float] = None) -> 'ScanResult':
        """Create ScanResult from ParsedServer"""
        return cls(
            ip=parsed.ip,
            port=parsed.port,
            success=True,
            server_data=cast(Dict[str, Any], asdict(parsed)),
            latency=latency
        )

@dataclass
class ScanStats:
    """Scanner statistics"""
    total_scanned: int = 0
    servers_found: int = 0
    blacklisted_skipped: int = 0
    errors: int = 0
    start_time: float = 0
    current_rate: float = 0

class ScannerModule(ABC):
    """Base class for scanner modules"""
    
    @abstractmethod
    async def initialize(self, scanner: 'MinecraftScanner') -> None:
        """Initialize the module with scanner instance"""
        pass
    
    @abstractmethod
    async def process_result(self, result: ScanResult) -> None:
        """Process a scan result"""
        pass
    
    @abstractmethod
    async def finalize(self) -> None:
        """Cleanup when scanning is complete"""
        pass

class MinecraftScanner:
    """
    Main scanner class with modular architecture
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = ConfigManager(config_path)
        
        # Create protocol config from scanner config
        protocol_config = ProtocolConfig.from_scanner_config(self.config.scanner)
        
        # Initialize components with proper config types
        self.db = DatabaseManager(DatabaseConfig(**vars(self.config.database)))
        self.protocol = MinecraftProtocol(protocol_config)
        
        # Import here to avoid circular imports
        from modules.discovery import IPDiscovery
        from modules.geolocation import GeolocationManager
        from modules.blacklist import BlacklistManager
        from modules.webhook import WebhookManager
        from parsers.server_parser import ServerResponseParser
        from utils.concurrency import ConnectionPool, RateLimiter
        from utils.memory import MemoryManager
        
        # Core managers with proper config types
        self.discovery = IPDiscovery(DiscoveryConfig(**vars(self.config.discovery)))
        self.geolocation = GeolocationManager(GeolocationConfig(**vars(self.config.geolocation)))
        self.blacklist = BlacklistManager(BlacklistConfig(**vars(self.config.blacklist)), self.db)
        self.webhook = WebhookManager(WebhookConfig(**vars(self.config.webhook)))
        self.parser = ServerResponseParser()
        
        # Convert shared config types to module-specific types
        module_concurrency_config = ModuleConcurrencyConfig(
            max_concurrent=self.config.concurrency.max_concurrent,
            batch_size=self.config.concurrency.batch_size,
            max_connections_per_host=self.config.concurrency.max_connections_per_host
        )
        
        module_memory_config = ModuleMemoryConfig(
            max_memory_mb=self.config.memory.max_memory_mb,
            gc_interval=self.config.memory.gc_interval,
            enable_monitoring=self.config.memory.enable_monitoring
        )
        
        # Utilities with module-specific config types
        self.connection_pool = ConnectionPool(module_concurrency_config)
        self.rate_limiter = RateLimiter(self.config.scanner.rate_limit)
        self.memory_manager = MemoryManager(module_memory_config)
        
        # State
        self.stats = ScanStats()
        self.running = False
        self.paused = False
        self.modules: List[ScannerModule] = []
        self.result_callback = None  # For real-time result reporting
        
        # Initialize components
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all components"""
        if self._initialized:
            return
            
        await self.db.initialize()
        await self.blacklist.initialize()
        await self.geolocation.initialize()
        
        # Initialize modules
        for module in self.modules:
            await module.initialize(self)
        
        self._initialized = True
        logger.info("Scanner initialized successfully")
    
    def add_module(self, module: ScannerModule) -> None:
        """Add a processing module"""
        self.modules.append(module)
    
    def set_result_callback(self, callback):
        """Register a callback to be called with each found server result"""
        self.result_callback = callback
    
    async def scan_range(self, ip_range: str) -> None:
        """Scan an IP range"""
        try:
            if not self._initialized:
                await self.initialize()
                
            self.running = True
            self.stats.start_time = time.time()
            
            logger.info(f"Starting scan of range: {ip_range}")
            
            # Generate IP targets
            targets = self.discovery.generate_targets(ip_range)
            
            # Process targets concurrently
            semaphore = asyncio.Semaphore(self.config.concurrency.max_concurrent)
            tasks = []
            
            async for target in targets:
                if not self.running:
                    break
                
                while self.paused:
                    await asyncio.sleep(0.1)
                
                # Check memory usage
                await self.memory_manager.check_usage()
                
                # Rate limiting
                await self.rate_limiter.acquire()
                
                # Create scan task
                task = asyncio.create_task(
                    self._scan_target_with_semaphore(semaphore, target)
                )
                tasks.append(task)
                
                # Process completed tasks periodically
                if len(tasks) >= self.config.concurrency.batch_size:
                    await self._process_completed_tasks(tasks)
                
                # Periodically send stats to webhook
                if self.webhook and self.webhook.enabled and self.stats.total_scanned % 1000 == 0:
                    try:
                        await self.webhook.send_scan_stats(self.stats)
                    except Exception as wh_exc:
                        logger.debug(f"Webhook stats notification failed: {wh_exc}")
            
            # Wait for remaining tasks
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            await self._finalize_scan()
            
            # Send scan completion notification
            if self.webhook and self.webhook.enabled:
                try:
                    await self.webhook.send_scan_complete(self.stats)
                except Exception as wh_exc:
                    logger.debug(f"Webhook completion notification failed: {wh_exc}")
            
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            raise ScannerError(f"Scan failed: {e}")
        finally:
            self.running = False
    
    async def _scan_target_with_semaphore(self, semaphore: asyncio.Semaphore, target: tuple) -> None:
        """Scan a single target with semaphore control"""
        async with semaphore:
            await self._scan_target(target)
    
    async def _scan_target(self, target: tuple) -> None:
        """Scan a single IP:port target with retry logic and robust error handling"""
        ip, port = target
        retries = getattr(self.protocol.config, 'retries', 0)
        attempt = 0
        while attempt <= retries:
            try:
                # Check blacklist
                if await self.blacklist.is_blacklisted(ip):
                    self.stats.blacklisted_skipped += 1
                    return

                # Perform the scan
                start_time = time.time()
                result = await self.protocol.ping_server(ip, port)
                latency = (time.time() - start_time) * 1000  # ms

                if result:
                    # Parse server response
                    server_data = await self.parser.parse_response(result)

                    # Geolocation lookup and storage
                    location_data = None
                    from dataclasses import asdict, is_dataclass
                    # Always convert to dict for augmentation
                    if is_dataclass(server_data):
                        server_data_dict = asdict(server_data)
                    elif isinstance(server_data, dict):
                        server_data_dict = server_data
                    else:
                        server_data_dict = dict(server_data) if server_data else {}
                    if self.geolocation and self.geolocation.enabled:
                        try:
                            location_data = await self.geolocation.get_location_data(ip)
                            if location_data:
                                await self.geolocation.save_location_data(self.db, location_data)
                                server_data_dict['country_code'] = location_data.country_code
                                server_data_dict['country_name'] = location_data.country_name
                                server_data_dict['region'] = location_data.region
                                server_data_dict['city'] = location_data.city
                                server_data_dict['latitude'] = location_data.latitude
                                server_data_dict['longitude'] = location_data.longitude
                                server_data_dict['isp'] = location_data.isp
                                server_data_dict['asn'] = location_data.asn
                                server_data_dict['asn_description'] = location_data.asn_description
                        except Exception as geo_exc:
                            logger.debug(f"Geolocation lookup failed for {ip}: {geo_exc}")
                    scan_result = ScanResult(
                        ip=ip,
                        port=port,
                        success=True,
                        server_data=server_data_dict,
                        latency=latency
                    )

                    # Store in database
                    await self.db.store_server(scan_result)

                    # Update statistics
                    self.stats.servers_found += 1

                    # Real-time result callback
                    if self.result_callback:
                        try:
                            self.result_callback(server_data_dict)
                        except Exception as cb_exc:
                            logger.debug(f"Result callback error: {cb_exc}")
                    # Webhook notification for found server
                    if self.webhook and self.webhook.enabled:
                        try:
                            await self.webhook.send_server_found(scan_result)
                        except Exception as wh_exc:
                            logger.debug(f"Webhook notification failed: {wh_exc}")
                    # Process through modules
                    for module in self.modules:
                        try:
                            await module.process_result(scan_result)
                        except Exception as e:
                            logger.warning(f"Module processing failed: {e}")

                    logger.info(f"Found server: {ip}:{port} ({server_data_dict.get('version_name', 'Unknown')})")
                    break  # Success, exit retry loop
                else:
                    attempt += 1
                    if attempt > retries:
                        # Do not increment errors for no response (just no server)
                        logger.debug(f"Scan found no server at {ip}:{port} after {retries+1} attempts (no response)")
                    else:
                        logger.debug(f"Scan found no server at {ip}:{port}, retrying ({attempt}/{retries})")
                    await asyncio.sleep(0.1 * attempt)
            except Exception as e:
                attempt += 1
                if attempt > retries:
                    self.stats.errors += 1
                    logger.debug(f"Scan failed for {ip}:{port} after {retries+1} attempts: {e}")
                else:
                    logger.debug(f"Scan error for {ip}:{port}, retrying ({attempt}/{retries}): {e}")
                await asyncio.sleep(0.1 * attempt)
        self.stats.total_scanned += 1
    
    async def _process_completed_tasks(self, tasks: List[asyncio.Task]) -> None:
        """Process completed tasks and remove them from the list"""
        completed = [task for task in tasks if task.done()]
        for task in completed:
            tasks.remove(task)
            try:
                await task
            except Exception as e:
                logger.debug(f"Task failed: {e}")
    
    async def _finalize_scan(self) -> None:
        """Finalize the scan"""
        # Finalize all modules
        for module in self.modules:
            try:
                await module.finalize()
            except Exception as e:
                logger.warning(f"Module finalization failed: {e}")
        
        # Update scan statistics
        elapsed = time.time() - self.stats.start_time
        self.stats.current_rate = self.stats.total_scanned / elapsed if elapsed > 0 else 0
        
        logger.info(f"Scan completed: {self.stats.servers_found} servers found "
                   f"in {elapsed:.1f}s ({self.stats.current_rate:.1f} IPs/sec)")
    
    def pause(self) -> None:
        """Pause the scanner"""
        self.paused = True
        logger.info("Scanner paused")
    
    def resume(self) -> None:
        """Resume the scanner"""
        self.paused = False
        logger.info("Scanner resumed")
    
    def stop(self) -> None:
        """Stop the scanner"""
        self.running = False
        logger.info("Scanner stopped")
    
    def get_stats(self) -> ScanStats:
        """Get current scanner statistics"""
        if self.stats.start_time > 0:
            elapsed = time.time() - self.stats.start_time
            self.stats.current_rate = self.stats.total_scanned / elapsed if elapsed > 0 else 0
        return self.stats 