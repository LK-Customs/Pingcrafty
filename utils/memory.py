"""
Memory management utilities
"""

import asyncio
import gc
import logging
import psutil
from typing import Dict, Any, Optional
from dataclasses import dataclass

from core.config_types import MemoryConfig

logger = logging.getLogger(__name__)

@dataclass
class MemoryConfig:
    max_memory_mb: int = 1000
    gc_interval: int = 1000
    enable_monitoring: bool = True
    warning_threshold: float = 0.8
    critical_threshold: float = 0.95

class MemoryManager:
    """Manages memory usage and cleanup"""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.max_memory = config.max_memory_mb * 1024 * 1024  # Convert to bytes
        self.scan_count = 0
        self.gc_count = 0
        self.last_cleanup = 0
        
        # Try to get process handle
        try:
            self.process = psutil.Process()
            self.monitoring_available = True
        except (ImportError, psutil.NoSuchProcess):
            self.monitoring_available = False
            logger.warning("psutil not available, memory monitoring disabled")
    
    async def check_usage(self) -> bool:
        """Check memory usage and perform cleanup if needed"""
        if not self.config.enable_monitoring or not self.monitoring_available:
            return True
        
        self.scan_count += 1
        
        # Check if it's time for cleanup
        if self.scan_count % self.config.gc_interval == 0:
            return await self._cleanup_if_needed()
        
        return True
    
    async def _cleanup_if_needed(self) -> bool:
        """Perform cleanup if memory usage is high"""
        try:
            current_memory = self.get_memory_usage()
            usage_ratio = current_memory / self.max_memory
            
            if usage_ratio >= self.config.critical_threshold:
                logger.critical(f"Critical memory usage: {usage_ratio:.1%}")
                await self._force_cleanup()
                return False
            elif usage_ratio >= self.config.warning_threshold:
                logger.warning(f"High memory usage: {usage_ratio:.1%}")
                await self._gentle_cleanup()
            
            return True
            
        except Exception as e:
            logger.error(f"Memory check failed: {e}")
            return True
    
    async def _gentle_cleanup(self) -> None:
        """Perform gentle memory cleanup"""
        try:
            # Run garbage collection
            collected = gc.collect()
            self.gc_count += 1
            
            # Brief pause to allow cleanup
            await asyncio.sleep(0.01)
            
            logger.info(f"Gentle cleanup: collected {collected} objects")
            
        except Exception as e:
            logger.error(f"Gentle cleanup failed: {e}")
    
    async def _force_cleanup(self) -> None:
        """Perform aggressive memory cleanup"""
        try:
            # Multiple GC passes
            total_collected = 0
            for _ in range(3):
                collected = gc.collect()
                total_collected += collected
                await asyncio.sleep(0.05)
            
            self.gc_count += 1
            
            # Clear any large data structures if available
            # This would be application-specific
            
            logger.warning(f"Force cleanup: collected {total_collected} objects")
            
        except Exception as e:
            logger.error(f"Force cleanup failed: {e}")
    
    def get_memory_usage(self) -> int:
        """Get current memory usage in bytes"""
        if not self.monitoring_available:
            return 0
        
        try:
            return self.process.memory_info().rss
        except Exception:
            return 0
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        current_memory = self.get_memory_usage()
        
        stats = {
            'current_mb': current_memory / 1024 / 1024,
            'max_mb': self.config.max_memory_mb,
            'usage_percentage': (current_memory / self.max_memory) * 100 if self.max_memory > 0 else 0,
            'scan_count': self.scan_count,
            'gc_count': self.gc_count,
            'monitoring_available': self.monitoring_available
        }
        
        if self.monitoring_available:
            try:
                memory_info = self.process.memory_info()
                stats.update({
                    'rss_mb': memory_info.rss / 1024 / 1024,
                    'vms_mb': memory_info.vms / 1024 / 1024,
                })
                
                # Add memory percentage if available
                memory_percent = self.process.memory_percent()
                stats['system_memory_percent'] = memory_percent
                
            except Exception as e:
                logger.debug(f"Failed to get detailed memory info: {e}")
        
        return stats
    
    async def monitor_continuously(self, interval: float = 60.0) -> None:
        """Continuously monitor memory usage"""
        if not self.monitoring_available:
            logger.warning("Memory monitoring not available")
            return
        
        while True:
            try:
                stats = self.get_memory_stats()
                usage = stats['usage_percentage']
                
                if usage > self.config.critical_threshold * 100:
                    logger.critical(f"Critical memory usage: {usage:.1f}%")
                elif usage > self.config.warning_threshold * 100:
                    logger.warning(f"High memory usage: {usage:.1f}%")
                else:
                    logger.debug(f"Memory usage: {usage:.1f}%")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
                await asyncio.sleep(interval)

class ObjectTracker:
    """Track object creation and deletion for memory debugging"""
    
    def __init__(self):
        self.tracked_objects = {}
        self.creation_counts = {}
        self.deletion_counts = {}
    
    def track_creation(self, obj_type: str, obj_id: str = None) -> None:
        """Track object creation"""
        if obj_id is None:
            obj_id = id(obj_type)
        
        self.tracked_objects[obj_id] = {
            'type': obj_type,
            'created_at': asyncio.get_event_loop().time()
        }
        
        self.creation_counts[obj_type] = self.creation_counts.get(obj_type, 0) + 1
    
    def track_deletion(self, obj_type: str, obj_id: str = None) -> None:
        """Track object deletion"""
        if obj_id is None:
            obj_id = id(obj_type)
        
        if obj_id in self.tracked_objects:
            del self.tracked_objects[obj_id]
        
        self.deletion_counts[obj_type] = self.deletion_counts.get(obj_type, 0) + 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get object tracking statistics"""
        return {
            'tracked_objects': len(self.tracked_objects),
            'creation_counts': self.creation_counts.copy(),
            'deletion_counts': self.deletion_counts.copy(),
            'net_counts': {
                obj_type: self.creation_counts.get(obj_type, 0) - self.deletion_counts.get(obj_type, 0)
                for obj_type in set(list(self.creation_counts.keys()) + list(self.deletion_counts.keys()))
            }
        } 