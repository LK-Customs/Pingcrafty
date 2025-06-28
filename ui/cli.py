"""
Command-line interface for headless operation
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class CLIInterface:
    """Command-line interface for headless operation"""
    
    def __init__(self, scanner):
        self.scanner = scanner
        self.running = True
        self.start_time = time.time()
        
        # Setup signal handlers
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}, stopping scanner...")
            self.scanner.stop()
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _print_banner(self) -> None:
        """Print application banner"""
        print("=" * 60)
        print("🎯 PingCrafty v0.2 - Minecraft Server Scanner")
        print("=" * 60)
        print()
    
    def _print_config(self) -> None:
        """Print current configuration"""
        config = self.scanner.config
        
        print("Configuration:")
        print(f"  Database: {config.database.type} ({config.database.path})")
        print(f"  Discovery: {config.discovery.method}")
        print(f"  Ports: {config.discovery.ports}")
        print(f"  Concurrency: {config.concurrency.max_concurrent}")
        print(f"  Rate Limit: {config.scanner.rate_limit}/s")
        print(f"  Timeout: {config.scanner.timeout}s")
        print(f"  Blacklist: {'Enabled' if config.blacklist.enabled else 'Disabled'}")
        print(f"  Geolocation: {'Enabled' if config.geolocation.enabled else 'Disabled'}")
        print()
    
    def _print_progress(self, stats) -> None:
        """Print scan progress"""
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        print(f"\rProgress: {stats.total_scanned:,} scanned | "
              f"{stats.servers_found:,} found | "
              f"{stats.current_rate:.1f} IPs/sec | "
              f"Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}", end="", flush=True)
    
    def _print_server_found(self, server_data: Dict[str, Any]) -> None:
        """Print found server information"""
        ip = server_data.get('ip', '')
        port = server_data.get('port', 25565)
        version = server_data.get('version_name', 'Unknown')
        software = server_data.get('server_type', 'Unknown')
        players = f"{server_data.get('online_players', 0)}/{server_data.get('max_players', 0)}"
        
        print(f"\n✅ Found: {ip}:{port} | {software} {version} | Players: {players}")
    
    def _print_final_stats(self, stats) -> None:
        """Print final scan statistics"""
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        print("\n")
        print("=" * 60)
        print("📊 Scan Results")
        print("=" * 60)
        print(f"Total IPs Scanned: {stats.total_scanned:,}")
        print(f"Servers Found: {stats.servers_found:,}")
        print(f"Blacklisted Skipped: {stats.blacklisted_skipped:,}")
        print(f"Errors: {stats.errors:,}")
        print(f"Average Rate: {stats.current_rate:.1f} IPs/sec")
        print(f"Total Time: {hours:02d}:{minutes:02d}:{seconds:02d}")
        
        if stats.servers_found > 0:
            success_rate = (stats.servers_found / stats.total_scanned) * 100
            print(f"Success Rate: {success_rate:.4f}%")
        
        print("=" * 60)
    
    async def run(self, ip_range: str) -> None:
        """Run the CLI interface"""
        try:
            self._print_banner()
            self._print_config()
            
            print(f"Starting scan of range: {ip_range}")
            print("Press Ctrl+C to stop the scan")
            print()
            
            # Setup progress reporting
            last_progress_time = time.time()
            progress_interval = 5.0  # Update every 5 seconds
            
            # Start scanner
            scanner_task = asyncio.create_task(
                self.scanner.scan_range(ip_range)
            )
            
            # Monitor progress
            while self.running and not scanner_task.done():
                await asyncio.sleep(1)
                
                # Print progress periodically
                current_time = time.time()
                if current_time - last_progress_time >= progress_interval:
                    stats = self.scanner.get_stats()
                    self._print_progress(stats)
                    last_progress_time = current_time
            
            # Wait for scanner to complete
            if not scanner_task.done():
                await scanner_task
            
            # Print final results
            final_stats = self.scanner.get_stats()
            self._print_final_stats(final_stats)
            
        except KeyboardInterrupt:
            print("\n\nScan interrupted by user")
            self.scanner.stop()
        except Exception as e:
            print(f"\nCLI Error: {e}")
            logger.error(f"CLI error: {e}")
        finally:
            self.running = False
    
    async def export_data(self, format_type: str = "json", output_file: Optional[str] = None) -> None:
        """Export scan data"""
        try:
            from ..utils.export import DataExporter
            
            exporter = DataExporter(self.scanner.db)
            
            if not output_file:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                output_file = f"pingcrafty_export_{timestamp}.{format_type}"
            
            print(f"Exporting data to {output_file}...")
            
            if format_type.lower() == "json":
                await exporter.export_json(output_file)
            elif format_type.lower() == "csv":
                await exporter.export_csv(output_file)
            elif format_type.lower() == "xlsx":
                await exporter.export_excel(output_file)
            else:
                print(f"Unsupported export format: {format_type}")
                return
            
            print(f"✅ Data exported successfully to {output_file}")
            
        except Exception as e:
            print(f"❌ Export failed: {e}")
            logger.error(f"Export error: {e}")
    
    async def import_blacklist(self, file_path: str) -> None:
        """Import blacklist from file"""
        try:
            print(f"Importing blacklist from {file_path}...")
            
            imported_count = await self.scanner.blacklist.import_from_file(file_path)
            
            print(f"✅ Successfully imported {imported_count} entries to blacklist")
            
        except Exception as e:
            print(f"❌ Blacklist import failed: {e}")
            logger.error(f"Blacklist import error: {e}")
    
    async def show_stats(self) -> None:
        """Show current database statistics"""
        try:
            # This would query the database for comprehensive stats
            print("📊 Database Statistics")
            print("-" * 40)
            
            # Get basic counts
            # This would need integration with database manager
            print("Total servers: N/A")
            print("Online mode servers: N/A") 
            print("Offline mode servers: N/A")
            print("Unique players seen: N/A")
            print("Total mods detected: N/A")
            
            print("-" * 40)
            
        except Exception as e:
            print(f"❌ Failed to get statistics: {e}")
            logger.error(f"Stats error: {e}")
    
    async def search_servers(self, query: str) -> None:
        """Search for servers by various criteria"""
        try:
            print(f"🔍 Searching for servers matching: {query}")
            print("-" * 40)
            
            # This would need integration with database search functionality
            print("Search functionality not yet implemented")
            
        except Exception as e:
            print(f"❌ Search failed: {e}")
            logger.error(f"Search error: {e}") 