"""
Network utilities and helpers
"""

import asyncio
import socket
import ipaddress
import logging
import time
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class NetworkConfig:
    timeout: float = 5.0
    max_retries: int = 3
    retry_delay: float = 1.0

class NetworkUtils:
    """Network utility functions"""
    
    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """Check if IP address is valid"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_valid_port(port: int) -> bool:
        """Check if port number is valid"""
        return 1 <= port <= 65535
    
    @staticmethod
    def is_private_ip(ip: str) -> bool:
        """Check if IP address is private"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj.is_private
        except ValueError:
            return False
    
    @staticmethod
    def is_reserved_ip(ip: str) -> bool:
        """Check if IP address is reserved"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            return (ip_obj.is_reserved or 
                   ip_obj.is_loopback or 
                   ip_obj.is_multicast or 
                   ip_obj.is_link_local)
        except ValueError:
            return False
    
    @staticmethod
    def expand_ip_range(ip_range: str) -> List[str]:
        """Expand IP range into individual IPs"""
        try:
            network = ipaddress.ip_network(ip_range, strict=False)
            return [str(ip) for ip in network.hosts()]
        except ValueError as e:
            logger.error(f"Invalid IP range {ip_range}: {e}")
            return []
    
    @staticmethod
    def get_network_info(ip: str) -> Dict[str, Any]:
        """Get network information for an IP"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            
            info = {
                'ip': str(ip_obj),
                'version': ip_obj.version,
                'is_private': ip_obj.is_private,
                'is_global': ip_obj.is_global,
                'is_reserved': ip_obj.is_reserved,
                'is_multicast': ip_obj.is_multicast,
                'is_loopback': ip_obj.is_loopback,
                'is_link_local': ip_obj.is_link_local
            }
            
            # Add network classification
            if ip_obj.is_private:
                info['classification'] = 'private'
            elif ip_obj.is_reserved:
                info['classification'] = 'reserved'
            elif ip_obj.is_multicast:
                info['classification'] = 'multicast'
            elif ip_obj.is_loopback:
                info['classification'] = 'loopback'
            else:
                info['classification'] = 'public'
            
            return info
            
        except ValueError as e:
            logger.error(f"Invalid IP address {ip}: {e}")
            return {}

class PortScanner:
    """Basic port scanning functionality"""
    
    def __init__(self, config: NetworkConfig = None):
        self.config = config or NetworkConfig()
    
    async def scan_port(self, ip: str, port: int) -> bool:
        """Scan a single port"""
        try:
            future = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(
                future, 
                timeout=self.config.timeout
            )
            
            writer.close()
            await writer.wait_closed()
            return True
            
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False
        except Exception as e:
            logger.debug(f"Port scan error for {ip}:{port}: {e}")
            return False
    
    async def scan_ports(self, ip: str, ports: List[int]) -> List[int]:
        """Scan multiple ports on a host"""
        open_ports = []
        
        tasks = []
        for port in ports:
            task = asyncio.create_task(self.scan_port(ip, port))
            tasks.append((port, task))
        
        for port, task in tasks:
            try:
                is_open = await task
                if is_open:
                    open_ports.append(port)
            except Exception as e:
                logger.debug(f"Port scan task failed for {ip}:{port}: {e}")
        
        return open_ports

class DNSResolver:
    """DNS resolution utilities"""
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
    
    async def resolve_hostname(self, hostname: str) -> Optional[str]:
        """Resolve hostname to IP address"""
        try:
            loop = asyncio.get_event_loop()
            addr_info = await asyncio.wait_for(
                loop.getaddrinfo(hostname, None, family=socket.AF_INET),
                timeout=self.timeout
            )
            
            if addr_info:
                return addr_info[0][4][0]  # First IPv4 address
            return None
            
        except (asyncio.TimeoutError, socket.gaierror) as e:
            logger.debug(f"DNS resolution failed for {hostname}: {e}")
            return None
        except Exception as e:
            logger.error(f"DNS resolution error for {hostname}: {e}")
            return None
    
    async def reverse_lookup(self, ip: str) -> Optional[str]:
        """Reverse DNS lookup"""
        try:
            loop = asyncio.get_event_loop()
            hostname = await asyncio.wait_for(
                loop.getnameinfo((ip, 0), socket.NI_NAMEREQD),
                timeout=self.timeout
            )
            
            return hostname[0]
            
        except (asyncio.TimeoutError, socket.herror) as e:
            logger.debug(f"Reverse DNS lookup failed for {ip}: {e}")
            return None
        except Exception as e:
            logger.error(f"Reverse DNS lookup error for {ip}: {e}")
            return None

class NetworkMonitor:
    """Monitor network performance and connectivity"""
    
    def __init__(self):
        self.stats = {
            'total_connections': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'timeouts': 0,
            'avg_latency': 0.0,
            'min_latency': float('inf'),
            'max_latency': 0.0
        }
        self.latencies = []
    
    def record_connection(self, success: bool, latency: Optional[float] = None, 
                         timeout: bool = False) -> None:
        """Record connection attempt"""
        self.stats['total_connections'] += 1
        
        if success:
            self.stats['successful_connections'] += 1
        else:
            self.stats['failed_connections'] += 1
        
        if timeout:
            self.stats['timeouts'] += 1
        
        if latency is not None:
            self.latencies.append(latency)
            self.stats['min_latency'] = min(self.stats['min_latency'], latency)
            self.stats['max_latency'] = max(self.stats['max_latency'], latency)
            self.stats['avg_latency'] = sum(self.latencies) / len(self.latencies)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get network statistics"""
        stats = self.stats.copy()
        
        if stats['total_connections'] > 0:
            stats['success_rate'] = (
                stats['successful_connections'] / stats['total_connections']
            ) * 100
            stats['failure_rate'] = (
                stats['failed_connections'] / stats['total_connections']
            ) * 100
            stats['timeout_rate'] = (
                stats['timeouts'] / stats['total_connections']
            ) * 100
        else:
            stats['success_rate'] = 0.0
            stats['failure_rate'] = 0.0
            stats['timeout_rate'] = 0.0
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset all statistics"""
        self.stats = {
            'total_connections': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'timeouts': 0,
            'avg_latency': 0.0,
            'min_latency': float('inf'),
            'max_latency': 0.0
        }
        self.latencies.clear()

class BandwidthLimiter:
    """Limit bandwidth usage"""
    
    def __init__(self, max_bytes_per_second: int):
        self.max_bytes_per_second = max_bytes_per_second
        self.bytes_used = 0
        self.last_reset = time.time()
        self.lock = asyncio.Lock()
    
    async def consume(self, bytes_count: int) -> None:
        """Consume bandwidth quota"""
        async with self.lock:
            now = time.time()
            
            # Reset counter every second
            if now - self.last_reset >= 1.0:
                self.bytes_used = 0
                self.last_reset = now
            
            # Check if we need to wait
            if self.bytes_used + bytes_count > self.max_bytes_per_second:
                wait_time = 1.0 - (now - self.last_reset)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    self.bytes_used = 0
                    self.last_reset = time.time()
            
            self.bytes_used += bytes_count 