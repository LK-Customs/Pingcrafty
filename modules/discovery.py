"""
IP discovery and target generation module
"""

import asyncio
import ipaddress
import logging
from typing import AsyncGenerator, Tuple, List, Optional
from abc import ABC, abstractmethod

from core.exceptions import DiscoveryError
from core.config_types import DiscoveryConfig

logger = logging.getLogger(__name__)

class TargetGenerator(ABC):
    """Base class for target generators"""
    
    @abstractmethod
    async def generate(self, target_spec: str) -> AsyncGenerator[Tuple[str, int], None]:
        """Generate IP:port targets"""
        pass

class RangeGenerator(TargetGenerator):
    """Generate targets from IP ranges"""
    
    def __init__(self, config: DiscoveryConfig):
        self.config = config
    
    async def generate(self, ip_range: str) -> AsyncGenerator[Tuple[str, int], None]:
        """Generate targets from IP range"""
        try:
            network = ipaddress.ip_network(ip_range, strict=False)
            
            batch = []
            for ip in network.hosts():
                for port in self.config.ports:
                    batch.append((str(ip), port))
                    
                    if len(batch) >= self.config.batch_size:
                        for target in batch:
                            yield target
                        batch = []
                        await asyncio.sleep(0)  # Yield control
            
            # Yield remaining targets
            for target in batch:
                yield target
                
        except ValueError as e:
            logger.error(f"Invalid IP range {ip_range}: {e}")
            raise DiscoveryError(f"Invalid IP range: {e}")

class MasscanGenerator(TargetGenerator):
    """Generate targets using masscan"""
    
    def __init__(self, config: DiscoveryConfig):
        self.config = config
    
    async def generate(self, ip_range: str) -> AsyncGenerator[Tuple[str, int], None]:
        """Generate targets using masscan"""
        try:
            # Build masscan command
            ports_str = ','.join(map(str, self.config.ports))
            cmd = [
                'masscan',
                ip_range,
                '-p', ports_str,
                '--rate', str(self.config.masscan_rate),
                '--excludefile', self.config.masscan_excludes,
                '-oG', '-'  # Output to stdout
            ]
            
            logger.info(f"Starting masscan: {' '.join(cmd)}")
            
            # Start masscan process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Parse output
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                line = line.decode('utf-8').strip()
                if line.startswith('Host:'):
                    # Parse masscan output: Host: IP () Ports: PORT/open/tcp//
                    parts = line.split()
                    if len(parts) >= 4:
                        ip = parts[1]
                        port_info = parts[3]
                        port = int(port_info.split('/')[0])
                        yield (ip, port)
            
            await process.wait()
            
        except Exception as e:
            logger.error(f"Masscan failed: {e}")
            raise DiscoveryError(f"Masscan execution failed: {e}")

class FileGenerator(TargetGenerator):
    """Generate targets from file"""
    
    def __init__(self, config: DiscoveryConfig):
        self.config = config
    
    async def generate(self, file_path: str) -> AsyncGenerator[Tuple[str, int], None]:
        """Generate targets from file"""
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                        
                    try:
                        if ':' in line:
                            ip, port = line.split(':', 1)
                            yield (ip.strip(), int(port.strip()))
                        else:
                            # IP only, use default ports
                            ip = line.strip()
                            # Validate IP
                            ipaddress.ip_address(ip)
                            for port in self.config.ports:
                                yield (ip, port)
                    except (ValueError, ipaddress.AddressValueError) as e:
                        logger.warning(f"Invalid entry on line {line_num}: {line} - {e}")
                        continue
                            
        except FileNotFoundError:
            raise DiscoveryError(f"Target file not found: {file_path}")
        except Exception as e:
            logger.error(f"File reading failed: {e}")
            raise DiscoveryError(f"File reading error: {e}")

class IPDiscovery:
    """IP discovery manager"""
    
    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self.generators = {
            'range': RangeGenerator(config),
            'masscan': MasscanGenerator(config),
            'file': FileGenerator(config)
        }
    
    async def generate_targets(self, target_spec: str) -> AsyncGenerator[Tuple[str, int], None]:
        """Generate targets using configured method"""
        generator = self.generators.get(self.config.method)
        if not generator:
            raise DiscoveryError(f"Unknown discovery method: {self.config.method}")
        
        logger.info(f"Starting target discovery using {self.config.method} method")
        target_count = 0
        
        async for target in generator.generate(target_spec):
            target_count += 1
            yield target
            
            # Log progress periodically
            if target_count % 10000 == 0:
                logger.info(f"Generated {target_count} targets")
        
        logger.info(f"Target generation complete: {target_count} total targets") 