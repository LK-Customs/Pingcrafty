"""
IP blacklist management module
"""

import asyncio
import logging
import time
import ipaddress
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass
from pathlib import Path
import aiofiles

from core.exceptions import BlacklistError

logger = logging.getLogger(__name__)

@dataclass
class BlacklistEntry:
    """Container for blacklist entry"""
    ip: str
    reason: Optional[str] = None
    added_by: str = "system"
    added_time: float = 0
    notes: Optional[str] = None

class BlacklistManager:
    """Manages IP blacklisting functionality"""
    
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.blacklist_cache: Set[str] = set()
        self.network_blacklist: Set[ipaddress.IPv4Network] = set()
        self.enabled = config.enabled
        self.auto_update = config.auto_update
        self.file_path = Path(config.file_path)
        self.last_update = 0
        self.update_interval = 3600  # 1 hour
        
    async def initialize(self) -> None:
        """Initialize blacklist manager"""
        if not self.enabled:
            logger.info("IP blacklist disabled")
            return
        
        # Load blacklist from database
        await self._load_from_database()
        
        # Load from file if exists
        if self.file_path.exists():
            await self._load_from_file()
        
        # Start auto-update task if enabled
        if self.auto_update:
            asyncio.create_task(self._auto_update_task())
        
        logger.info(f"Blacklist initialized: {len(self.blacklist_cache)} IPs, {len(self.network_blacklist)} networks")
    
    async def is_blacklisted(self, ip: str) -> bool:
        """Check if an IP is blacklisted"""
        if not self.enabled:
            return False
        
        # Direct IP check
        if ip in self.blacklist_cache:
            return True
        
        # Network range check
        try:
            ip_obj = ipaddress.ip_address(ip)
            for network in self.network_blacklist:
                if ip_obj in network:
                    return True
        except ipaddress.AddressValueError:
            logger.warning(f"Invalid IP address for blacklist check: {ip}")
            return False
        
        return False
    
    async def add_ip(self, ip: str, reason: str = "Manual", notes: str = "") -> bool:
        """Add an IP to the blacklist"""
        try:
            # Validate IP
            ipaddress.ip_address(ip)
            
            # Add to cache
            self.blacklist_cache.add(ip)
            
            # Add to database
            success = await self._add_to_database(ip, reason, notes)
            if success:
                logger.info(f"Added {ip} to blacklist: {reason}")
                return True
            else:
                # Remove from cache if database failed
                self.blacklist_cache.discard(ip)
                return False
                
        except ipaddress.AddressValueError:
            logger.error(f"Invalid IP address: {ip}")
            return False
        except Exception as e:
            logger.error(f"Error adding {ip} to blacklist: {e}")
            return False
    
    async def add_network(self, network: str, reason: str = "Network block", notes: str = "") -> bool:
        """Add a network range to the blacklist"""
        try:
            # Validate and create network object
            network_obj = ipaddress.ip_network(network, strict=False)
            
            # Prevent adding overly large networks
            if network_obj.num_addresses > 65536:  # /16 or larger
                logger.warning(f"Network {network} too large ({network_obj.num_addresses} addresses)")
                return False
            
            # Add to network blacklist
            self.network_blacklist.add(network_obj)
            
            # Store in database (as a special network entry)
            success = await self._add_network_to_database(str(network_obj), reason, notes)
            if success:
                logger.info(f"Added network {network_obj} to blacklist: {reason}")
                return True
            else:
                # Remove from cache if database failed
                self.network_blacklist.discard(network_obj)
                return False
                
        except ipaddress.AddressValueError:
            logger.error(f"Invalid network: {network}")
            return False
        except Exception as e:
            logger.error(f"Error adding network {network} to blacklist: {e}")
            return False
    
    async def remove_ip(self, ip: str) -> bool:
        """Remove an IP from the blacklist"""
        try:
            # Remove from cache
            self.blacklist_cache.discard(ip)
            
            # Remove from database
            success = await self._remove_from_database(ip)
            if success:
                logger.info(f"Removed {ip} from blacklist")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing {ip} from blacklist: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get blacklist statistics"""
        try:
            stats = await self._get_database_stats()
            stats['cached_ips'] = len(self.blacklist_cache)
            stats['cached_networks'] = len(self.network_blacklist)
            return stats
        except Exception as e:
            logger.error(f"Error getting blacklist stats: {e}")
            return {
                'total_ips': 0,
                'cached_ips': len(self.blacklist_cache),
                'cached_networks': len(self.network_blacklist),
                'top_reasons': []
            }
    
    async def export_to_file(self, file_path: Optional[str] = None) -> bool:
        """Export blacklist to file"""
        if not file_path:
            file_path = self.file_path
        
        try:
            # Get all blacklisted IPs from database
            blacklist_data = await self._get_all_from_database()
            
            async with aiofiles.open(file_path, 'w') as f:
                await f.write("# PingCrafty IP Blacklist Export\n")
                await f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                await f.write("# Format: IP/Network, Reason, Added Time, Notes\n\n")
                
                for entry in blacklist_data:
                    ip, reason, added_time, notes = entry
                    notes = notes or ""
                    await f.write(f"{ip},{reason},{added_time},{notes}\n")
            
            logger.info(f"Exported {len(blacklist_data)} entries to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting blacklist: {e}")
            return False
    
    async def import_from_file(self, file_path: Optional[str] = None) -> int:
        """Import blacklist from file"""
        if not file_path:
            file_path = self.file_path
        
        imported_count = 0
        try:
            async with aiofiles.open(file_path, 'r') as f:
                async for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    try:
                        parts = line.split(',', 3)
                        if len(parts) >= 2:
                            ip_or_network = parts[0].strip()
                            reason = parts[1].strip()
                            notes = parts[3].strip() if len(parts) > 3 else ""
                            
                            # Try to add as network first, then as IP
                            if '/' in ip_or_network:
                                success = await self.add_network(ip_or_network, reason, notes)
                            else:
                                success = await self.add_ip(ip_or_network, reason, notes)
                            
                            if success:
                                imported_count += 1
                                
                    except Exception as e:
                        logger.warning(f"Error importing line '{line}': {e}")
                        continue
            
            logger.info(f"Imported {imported_count} entries from {file_path}")
            return imported_count
            
        except FileNotFoundError:
            logger.warning(f"Blacklist file not found: {file_path}")
            return 0
        except Exception as e:
            logger.error(f"Error importing blacklist: {e}")
            return 0
    
    async def _load_from_database(self) -> None:
        """Load blacklist from database"""
        try:
            # Load regular IPs
            query = "SELECT ip FROM ip_blacklist WHERE ip NOT LIKE '%/%'"
            rows = await self._execute_query(query)
            for row in rows:
                self.blacklist_cache.add(row[0])
            
            # Load network ranges
            query = "SELECT ip FROM ip_blacklist WHERE ip LIKE '%/%'"
            rows = await self._execute_query(query)
            for row in rows:
                try:
                    network = ipaddress.ip_network(row[0], strict=False)
                    self.network_blacklist.add(network)
                except ipaddress.AddressValueError:
                    logger.warning(f"Invalid network in database: {row[0]}")
                    
        except Exception as e:
            logger.error(f"Error loading blacklist from database: {e}")
    
    async def _load_from_file(self) -> None:
        """Load additional entries from file"""
        try:
            imported = await self.import_from_file()
            logger.info(f"Loaded {imported} additional entries from file")
        except Exception as e:
            logger.error(f"Error loading from file: {e}")
    
    async def _auto_update_task(self) -> None:
        """Background task for auto-updating blacklist"""
        while True:
            try:
                await asyncio.sleep(self.update_interval)
                
                # Check if file has been modified
                if self.file_path.exists():
                    file_mtime = self.file_path.stat().st_mtime
                    if file_mtime > self.last_update:
                        logger.info("Blacklist file updated, reloading...")
                        await self._load_from_file()
                        self.last_update = file_mtime
                        
            except Exception as e:
                logger.error(f"Error in auto-update task: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _add_to_database(self, ip: str, reason: str, notes: str) -> bool:
        """Add IP to database"""
        try:
            query = """
                INSERT OR REPLACE INTO ip_blacklist (ip, reason, notes, added_time)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """
            return await self._execute_insert(query, (ip, reason, notes))
        except Exception as e:
            logger.error(f"Database error adding {ip}: {e}")
            return False
    
    async def _add_network_to_database(self, network: str, reason: str, notes: str) -> bool:
        """Add network to database"""
        return await self._add_to_database(network, reason, notes)
    
    async def _remove_from_database(self, ip: str) -> bool:
        """Remove IP from database"""
        try:
            query = "DELETE FROM ip_blacklist WHERE ip = ?"
            return await self._execute_insert(query, (ip,))
        except Exception as e:
            logger.error(f"Database error removing {ip}: {e}")
            return False
    
    async def _get_database_stats(self) -> Dict[str, Any]:
        """Get statistics from database"""
        try:
            # Total count
            query = "SELECT COUNT(*) FROM ip_blacklist"
            rows = await self._execute_query(query)
            total_count = rows[0][0] if rows else 0
            
            # Top reasons
            query = """
                SELECT reason, COUNT(*) as count
                FROM ip_blacklist
                GROUP BY reason
                ORDER BY count DESC
                LIMIT 5
            """
            top_reasons = await self._execute_query(query)
            
            return {
                'total_ips': total_count,
                'top_reasons': list(top_reasons)
            }
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {'total_ips': 0, 'top_reasons': []}
    
    async def _get_all_from_database(self) -> List[tuple]:
        """Get all blacklist entries from database"""
        try:
            query = """
                SELECT ip, reason, added_time, notes
                FROM ip_blacklist
                ORDER BY added_time DESC
            """
            return await self._execute_query(query)
        except Exception as e:
            logger.error(f"Error getting all blacklist entries: {e}")
            return []
    
    async def _execute_query(self, query: str, params: tuple = ()) -> List[tuple]:
        """Execute a SELECT query"""
        # This would use the database manager
        # Implementation depends on the database backend
        return []
    
    async def _execute_insert(self, query: str, params: tuple = ()) -> bool:
        """Execute an INSERT/UPDATE/DELETE query"""
        # This would use the database manager
        # Implementation depends on the database backend
        return True 