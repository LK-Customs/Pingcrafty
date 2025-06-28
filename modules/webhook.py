"""
Webhook integration module for notifications
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from core.exceptions import WebhookError

logger = logging.getLogger(__name__)

@dataclass
class WebhookMessage:
    """Container for webhook message data"""
    content: Optional[str] = None
    embeds: Optional[List[Dict[str, Any]]] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None

class WebhookManager:
    """Manages webhook notifications"""
    
    def __init__(self, config):
        self.config = config
        self.enabled = config.enabled
        self.url = config.url
        self.batch_size = config.batch_size
        self.include_stats = config.include_stats
        
        # Internal state
        self.session = None
        self.message_queue: List[WebhookMessage] = []
        self.stats_data = {}
        self.last_stats_update = 0
        self.rate_limit_delay = 1.0  # Discord rate limit
        self.last_request_time = 0
        
        # Initialize if enabled
        if self.enabled and not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, webhook functionality disabled")
            self.enabled = False
    
    async def initialize(self) -> None:
        """Initialize webhook manager"""
        if not self.enabled:
            logger.info("Webhook notifications disabled")
            return
        
        if not self.url:
            logger.warning("Webhook URL not configured, disabling webhooks")
            self.enabled = False
            return
        
        try:
            self.session = aiohttp.ClientSession()
            
            # Test webhook
            await self._send_test_message()
            
            # Start background processing
            asyncio.create_task(self._process_queue())
            
            logger.info("Webhook manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize webhook manager: {e}")
            self.enabled = False
    
    async def send_server_found(self, scan_result) -> None:
        """Send notification for found server"""
        if not self.enabled:
            return
        
        try:
            embed = self._create_server_embed(scan_result)
            message = WebhookMessage(embeds=[embed])
            
            await self._queue_message(message)
            
        except Exception as e:
            logger.error(f"Error creating server notification: {e}")
    
    async def send_scan_stats(self, stats) -> None:
        """Send scan statistics"""
        if not self.enabled or not self.include_stats:
            return
        
        # Rate limit stats updates (max once per minute)
        now = time.time()
        if now - self.last_stats_update < 60:
            return
        
        try:
            embed = self._create_stats_embed(stats)
            message = WebhookMessage(embeds=[embed])
            
            await self._queue_message(message)
            self.last_stats_update = now
            
        except Exception as e:
            logger.error(f"Error creating stats notification: {e}")
    
    async def send_scan_complete(self, final_stats) -> None:
        """Send scan completion notification"""
        if not self.enabled:
            return
        
        try:
            embed = self._create_completion_embed(final_stats)
            message = WebhookMessage(embeds=[embed])
            
            await self._send_message_immediate(message)
            
        except Exception as e:
            logger.error(f"Error sending completion notification: {e}")
    
    async def send_custom_message(self, content: str, embed: Optional[Dict[str, Any]] = None) -> None:
        """Send custom message"""
        if not self.enabled:
            return
        
        try:
            embeds = [embed] if embed else None
            message = WebhookMessage(content=content, embeds=embeds)
            
            await self._queue_message(message)
            
        except Exception as e:
            logger.error(f"Error sending custom message: {e}")
    
    def _create_server_embed(self, scan_result) -> Dict[str, Any]:
        """Create Discord embed for found server"""
        server_data = scan_result.server_data or {}
        
        # Determine embed color based on server type
        color_map = {
            'vanilla': 0x00AA00,    # Green
            'paper': 0xFF6600,      # Orange
            'spigot': 0xFFAA00,     # Yellow
            'forge': 0x1E90FF,      # Blue
            'fabric': 0x8B4513,     # Brown
            'bungeecord': 0x800080, # Purple
            'velocity': 0x00FFFF,   # Cyan
            'unknown': 0x808080     # Gray
        }
        
        server_type = server_data.get('server_type', 'unknown')
        color = color_map.get(server_type, 0x808080)
        
        # Build fields
        fields = []
        
        # Version info
        if server_data.get('version_name'):
            fields.append({
                'name': 'Version',
                'value': server_data['version_name'],
                'inline': True
            })
        
        # Server software
        if server_type != 'unknown':
            fields.append({
                'name': 'Software',
                'value': server_type.title(),
                'inline': True
            })
        
        # Player count
        online = server_data.get('online_players', 0)
        max_players = server_data.get('max_players', 0)
        if max_players > 0:
            fields.append({
                'name': 'Players',
                'value': f"{online}/{max_players}",
                'inline': True
            })
        
        # Latency
        if scan_result.latency:
            fields.append({
                'name': 'Latency',
                'value': f"{scan_result.latency:.0f}ms",
                'inline': True
            })
        
        # MOTD
        motd = server_data.get('motd_formatted', server_data.get('motd_raw'))
        if motd:
            # Truncate long MOTDs
            if len(motd) > 1000:
                motd = motd[:997] + "..."
            fields.append({
                'name': 'MOTD',
                'value': motd,
                'inline': False
            })
        
        # Mods (if any)
        mods = server_data.get('mods', [])
        if mods:
            mod_list = [f"{mod.get('id', 'unknown')} ({mod.get('version', 'unknown')})" for mod in mods[:5]]
            if len(mods) > 5:
                mod_list.append(f"... and {len(mods) - 5} more")
            
            fields.append({
                'name': 'Mods',
                'value': '\n'.join(mod_list),
                'inline': False
            })
        
        return {
            'title': f"🎮 Minecraft Server Found",
            'description': f"**{scan_result.ip}:{scan_result.port}**",
            'color': color,
            'fields': fields,
            'timestamp': datetime.utcnow().isoformat(),
            'footer': {
                'text': 'PingCrafty v0.2'
            }
        }
    
    def _create_stats_embed(self, stats) -> Dict[str, Any]:
        """Create Discord embed for scan statistics"""
        fields = [
            {
                'name': '📊 Progress',
                'value': f"{stats.total_scanned:,} IPs scanned",
                'inline': True
            },
            {
                'name': '🎯 Found',
                'value': f"{stats.servers_found:,} servers",
                'inline': True
            },
            {
                'name': '⚡ Rate',
                'value': f"{stats.current_rate:.1f} IPs/sec",
                'inline': True
            }
        ]
        
        if stats.blacklisted_skipped > 0:
            fields.append({
                'name': '🚫 Blacklisted',
                'value': f"{stats.blacklisted_skipped:,} skipped",
                'inline': True
            })
        
        if stats.errors > 0:
            fields.append({
                'name': '❌ Errors',
                'value': f"{stats.errors:,}",
                'inline': True
            })
        
        # Calculate elapsed time
        elapsed = time.time() - stats.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        fields.append({
            'name': '⏱️ Elapsed',
            'value': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            'inline': True
        })
        
        return {
            'title': '📈 Scan Statistics',
            'color': 0x00AA00,
            'fields': fields,
            'timestamp': datetime.utcnow().isoformat(),
            'footer': {
                'text': 'PingCrafty v0.2 - Live Stats'
            }
        }
    
    def _create_completion_embed(self, final_stats) -> Dict[str, Any]:
        """Create Discord embed for scan completion"""
        elapsed = time.time() - final_stats.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        fields = [
            {
                'name': '📊 Total Scanned',
                'value': f"{final_stats.total_scanned:,} IPs",
                'inline': True
            },
            {
                'name': '🎯 Servers Found',
                'value': f"{final_stats.servers_found:,}",
                'inline': True
            },
            {
                'name': '⚡ Average Rate',
                'value': f"{final_stats.current_rate:.1f} IPs/sec",
                'inline': True
            },
            {
                'name': '⏱️ Total Time',
                'value': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
                'inline': True
            }
        ]
        
        if final_stats.blacklisted_skipped > 0:
            fields.append({
                'name': '🚫 Blacklisted',
                'value': f"{final_stats.blacklisted_skipped:,} skipped",
                'inline': True
            })
        
        if final_stats.errors > 0:
            fields.append({
                'name': '❌ Errors',
                'value': f"{final_stats.errors:,}",
                'inline': True
            })
        
        return {
            'title': '✅ Scan Complete!',
            'description': f"Successfully completed scanning with {final_stats.servers_found:,} servers discovered.",
            'color': 0x00FF00,
            'fields': fields,
            'timestamp': datetime.utcnow().isoformat(),
            'footer': {
                'text': 'PingCrafty v0.2'
            }
        }
    
    async def _queue_message(self, message: WebhookMessage) -> None:
        """Add message to queue for batch processing"""
        self.message_queue.append(message)
        
        # If queue is full, process immediately
        if len(self.message_queue) >= self.batch_size:
            await self._process_queue()
    
    async def _process_queue(self) -> None:
        """Process queued messages"""
        while True:
            try:
                if self.message_queue:
                    # Process up to batch_size messages
                    batch = self.message_queue[:self.batch_size]
                    self.message_queue = self.message_queue[self.batch_size:]
                    
                    for message in batch:
                        await self._send_message_immediate(message)
                        
                        # Rate limiting
                        await asyncio.sleep(self.rate_limit_delay)
                
                # Wait before checking queue again
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error processing webhook queue: {e}")
                await asyncio.sleep(10)
    
    async def _send_message_immediate(self, message: WebhookMessage) -> bool:
        """Send message immediately"""
        if not self.session:
            return False
        
        try:
            # Rate limiting
            now = time.time()
            if now - self.last_request_time < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - (now - self.last_request_time))
            
            # Prepare payload
            payload = {}
            if message.content:
                payload['content'] = message.content
            if message.embeds:
                payload['embeds'] = message.embeds
            if message.username:
                payload['username'] = message.username
            if message.avatar_url:
                payload['avatar_url'] = message.avatar_url
            
            # Send request
            async with self.session.post(
                self.url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            ) as response:
                self.last_request_time = time.time()
                
                if response.status == 204:
                    return True
                elif response.status == 429:
                    # Rate limited
                    retry_after = float(response.headers.get('retry-after', 1))
                    logger.warning(f"Webhook rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    return False
                else:
                    logger.warning(f"Webhook request failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending webhook message: {e}")
            return False
    
    async def _send_test_message(self) -> None:
        """Send test message to verify webhook"""
        message = WebhookMessage(
            content="🚀 PingCrafty v0.2 webhook initialized successfully!",
            embeds=[{
                'title': 'Test Message',
                'description': 'Webhook is working correctly.',
                'color': 0x00AA00,
                'timestamp': datetime.utcnow().isoformat(),
                'footer': {'text': 'PingCrafty v0.2'}
            }]
        )
        
        success = await self._send_message_immediate(message)
        if not success:
            raise WebhookError("Failed to send test message")
    
    async def close(self) -> None:
        """Cleanup resources"""
        if self.session:
            await self.session.close() 