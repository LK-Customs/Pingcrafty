"""
Concurrency management utilities
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from core.config_types import ConcurrencyConfig

logger = logging.getLogger(__name__)

@dataclass
class ConcurrencyConfig:
    max_concurrent: int = 1000
    batch_size: int = 100
    max_connections_per_host: int = 10
    rate_limit: int = 1000

class ConnectionPool:
    """Manages connection pooling and limits"""
    
    def __init__(self, config: ConcurrencyConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent)
        self.host_semaphores: Dict[str, asyncio.Semaphore] = {}
        self.active_connections = 0
        self.total_connections = 0
        self.failed_connections = 0
        
    async def acquire(self, host: Optional[str] = None) -> None:
        """Acquire connection from pool"""
        await self.semaphore.acquire()
        
        if host and self.config.max_connections_per_host > 0:
            if host not in self.host_semaphores:
                self.host_semaphores[host] = asyncio.Semaphore(
                    self.config.max_connections_per_host
                )
            await self.host_semaphores[host].acquire()
        
        self.active_connections += 1
        self.total_connections += 1
    
    def release(self, host: Optional[str] = None, failed: bool = False) -> None:
        """Release connection back to pool"""
        self.semaphore.release()
        
        if host and host in self.host_semaphores:
            self.host_semaphores[host].release()
        
        self.active_connections -= 1
        if failed:
            self.failed_connections += 1
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        failed = exc_type is not None
        self.release(failed=failed)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        return {
            'active_connections': self.active_connections,
            'total_connections': self.total_connections,
            'failed_connections': self.failed_connections,
            'max_concurrent': self.config.max_concurrent,
            'success_rate': (
                (self.total_connections - self.failed_connections) / 
                max(self.total_connections, 1)
            ) * 100
        }

class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, rate: int, burst: Optional[int] = None):
        self.rate = rate  # tokens per second
        self.burst = burst or rate  # max tokens in bucket
        self.tokens = float(self.burst)
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from the rate limiter"""
        async with self.lock:
            now = time.time()
            
            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return
            
            # Calculate wait time for required tokens
            wait_time = (tokens - self.tokens) / self.rate
            
        # Wait outside the lock to avoid blocking other requests
        await asyncio.sleep(wait_time)
        
        # Try again after waiting
        await self.acquire(tokens)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics"""
        return {
            'current_tokens': self.tokens,
            'max_tokens': self.burst,
            'rate_per_second': self.rate,
            'utilization': (1 - self.tokens / self.burst) * 100
        }

class BatchProcessor:
    """Process items in batches with concurrency control"""
    
    def __init__(self, batch_size: int = 100, max_concurrent_batches: int = 10):
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrent_batches)
        self.processed_count = 0
        
    async def process(self, items, processor_func):
        """Process items in batches"""
        batches = [items[i:i + self.batch_size] 
                  for i in range(0, len(items), self.batch_size)]
        
        tasks = []
        for batch in batches:
            task = asyncio.create_task(
                self._process_batch(batch, processor_func)
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_batch(self, batch, processor_func):
        """Process a single batch"""
        async with self.semaphore:
            for item in batch:
                try:
                    await processor_func(item)
                    self.processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing item: {e}") 