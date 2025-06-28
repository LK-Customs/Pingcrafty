"""
Rich console interface with real-time progress display
"""

import asyncio
import time
import threading
import sys
import logging
from typing import Optional, Dict, Any, List

from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.progress import Progress, TaskID, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.tree import Tree

# Platform-specific imports for keyboard handling
if sys.platform.startswith('win'):
    import msvcrt
else:
    try:
        import select
        import termios
        import tty
    except ImportError:
        select = None
        termios = None
        tty = None

logger = logging.getLogger(__name__)

class ConsoleUI:
    """Rich console interface with real-time updates"""
    
    def __init__(self, scanner):
        self.scanner = scanner
        self.console = Console()
        self.layout = Layout()
        self.running = True
        self.paused = False
        
        # Input handling
        self.input_thread = None
        self.key_queue = []
        self.original_settings = None
        
        # Progress tracking
        self.scan_progress = None
        self.scan_task_id = None
        
        # Statistics
        self.start_time = time.time()
        self.last_update = time.time()
        self.recent_servers = []
        
        # Setup layout
        self._setup_layout()
        self._setup_logging()
    
    def _setup_layout(self) -> None:
        """Setup the rich layout structure"""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=6)
        )
        
        self.layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        self.layout["left"].split_column(
            Layout(name="progress", size=8),
            Layout(name="stats", size=12),
            Layout(name="recent", ratio=1)
        )
    
    def _setup_logging(self) -> None:
        """Setup logging to prevent console interference"""
        # Disable console logging during UI operation
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler):
                root_logger.removeHandler(handler)
        
        # Add file handler only
        file_handler = logging.FileHandler('logs/pingcrafty_ui.log')
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.INFO)
    
    def _setup_terminal_input(self) -> None:
        """Setup terminal for non-blocking input"""
        if not sys.platform.startswith('win') and termios and tty:
            try:
                self.original_settings = termios.tcgetattr(sys.stdin)
                tty.setraw(sys.stdin.fileno())
            except Exception:
                pass
    
    def _restore_terminal_input(self) -> None:
        """Restore original terminal settings"""
        if not sys.platform.startswith('win') and termios and self.original_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.original_settings)
            except Exception:
                pass
    
    def _get_char_non_blocking(self) -> Optional[str]:
        """Get character from stdin without blocking"""
        try:
            if sys.platform.startswith('win'):
                if msvcrt.kbhit():
                    char = msvcrt.getch()
                    if char == b'\x00' or char == b'\xe0':
                        msvcrt.getch()  # Consume second byte
                        return None
                    return char.decode('utf-8', errors='ignore')
                return None
            else:
                if select and select.select([sys.stdin], [], [], 0.0)[0]:
                    return sys.stdin.read(1)
                return None
        except Exception:
            return None
    
    def _input_handler_thread(self) -> None:
        """Thread to handle keyboard input"""
        while self.running:
            try:
                char = self._get_char_non_blocking()
                if char:
                    self.key_queue.append(char.lower())
                time.sleep(0.1)
            except Exception:
                time.sleep(0.1)
    
    def _process_keyboard_input(self) -> None:
        """Process keyboard input from queue"""
        while self.key_queue:
            key = self.key_queue.pop(0)
            if key == 'p':
                self._toggle_pause()
            elif key == 's':
                self._stop_scan()
            elif key == 'q':
                self._quit_application()
            elif key == 'r':
                self._restart_scan()
            elif key == 'e':
                self._export_data()
    
    def _toggle_pause(self) -> None:
        """Toggle pause/resume"""
        if self.scanner.paused:
            self.scanner.resume()
            self.paused = False
        else:
            self.scanner.pause()
            self.paused = True
    
    def _stop_scan(self) -> None:
        """Stop the current scan"""
        self.scanner.stop()
    
    def _quit_application(self) -> None:
        """Quit the application"""
        self.scanner.stop()
        self.running = False
    
    def _restart_scan(self) -> None:
        """Restart the scan"""
        # This would need integration with the scanner restart functionality
        pass
    
    def _export_data(self) -> None:
        """Export scan data"""
        # This would trigger data export functionality
        pass
    
    def _create_header(self) -> Panel:
        """Create header panel"""
        status_text = "PAUSED" if self.paused else "RUNNING" if self.scanner.running else "STOPPED"
        status_color = "yellow" if self.paused else "green" if self.scanner.running else "red"
        
        title = Text.assemble(
            ("🎯 PingCrafty v0.2 - ", "bold blue"),
            ("Minecraft Server Scanner ", "blue"),
            (f"[{status_text}]", status_color)
        )
        
        return Panel(
            Align.center(title),
            style="bold"
        )
    
    def _create_progress_panel(self) -> Panel:
        """Create progress panel with progress bars"""
        if not self.scan_progress:
            self.scan_progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                expand=True
            )
            self.scan_task_id = self.scan_progress.add_task("Scanning...", total=100)
        
        # Update progress
        stats = self.scanner.get_stats()
        if stats.total_scanned > 0:
            # This would need to be calculated based on the target range
            estimated_total = 1000000  # Placeholder
            percentage = (stats.total_scanned / estimated_total) * 100
            self.scan_progress.update(
                self.scan_task_id,
                completed=percentage,
                description=f"Scanned {stats.total_scanned:,} IPs"
            )
        
        return Panel(
            self.scan_progress,
            title="📊 Scan Progress",
            border_style="blue"
        )
    
    def _create_stats_panel(self) -> Panel:
        """Create statistics panel"""
        stats = self.scanner.get_stats()
        elapsed = time.time() - self.start_time
        
        stats_table = Table(show_header=False, box=None, expand=True)
        stats_table.add_column("Metric", style="cyan", width=16)
        stats_table.add_column("Value", style="white")
        
        # Basic statistics
        stats_table.add_row("Total Scanned:", f"{stats.total_scanned:,}")
        stats_table.add_row("Servers Found:", f"{stats.servers_found:,}")
        stats_table.add_row("Blacklisted:", f"{stats.blacklisted_skipped:,}")
        stats_table.add_row("Errors:", f"{stats.errors:,}")
        
        # Performance metrics
        rate_color = "green" if stats.current_rate > 1000 else "yellow" if stats.current_rate > 100 else "red"
        rate_text = Text(f"{stats.current_rate:.1f} IPs/sec", style=rate_color)
        stats_table.add_row("Scan Rate:", rate_text)
        
        # Time information
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        elapsed_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        stats_table.add_row("Elapsed:", elapsed_text)
        
        # Memory usage (if available)
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_text = f"{memory_mb:.1f} MB"
            stats_table.add_row("Memory:", memory_text)
        except ImportError:
            pass
        
        return Panel(
            stats_table,
            title="📈 Statistics",
            border_style="green"
        )
    
    def _create_recent_servers_panel(self) -> Panel:
        """Create recent servers panel"""
        servers_table = Table(show_header=True, header_style="bold magenta")
        servers_table.add_column("IP:Port", style="cyan", width=18)
        servers_table.add_column("Version", style="green", width=12)
        servers_table.add_column("Software", style="blue", width=10)
        servers_table.add_column("Players", style="yellow", width=8)
        
        # Get recent servers (this would need integration with the scanner)
        for server in self.recent_servers[-10:]:  # Show last 10
            ip_port = f"{server.get('ip', '')}:{server.get('port', 25565)}"
            version = server.get('version', 'Unknown')[:12]
            software = server.get('software', 'Unknown')[:10]
            players = f"{server.get('online_players', 0)}/{server.get('max_players', 0)}"
            
            servers_table.add_row(ip_port, version, software, players)
        
        # Fill empty rows
        while len(servers_table.rows) < 5:
            servers_table.add_row("", "", "", "")
        
        return Panel(
            servers_table,
            title="🎮 Recent Servers",
            border_style="blue"
        )
    
    def _create_config_panel(self) -> Panel:
        """Create configuration panel"""
        config_tree = Tree("⚙️ Configuration")
        
        # Scanner config
        scanner_node = config_tree.add("🔍 Scanner")
        scanner_node.add(f"Timeout: {self.scanner.config.scanner.timeout}s")
        scanner_node.add(f"Protocol: {self.scanner.config.scanner.protocol_version}")
        scanner_node.add(f"Retries: {self.scanner.config.scanner.retries}")
        scanner_node.add(f"Rate Limit: {self.scanner.config.scanner.rate_limit}/s")
        
        # Discovery config
        discovery_node = config_tree.add("🎯 Discovery")
        discovery_node.add(f"Method: {self.scanner.config.discovery.method}")
        discovery_node.add(f"Ports: {self.scanner.config.discovery.ports}")
        discovery_node.add(f"Batch Size: {self.scanner.config.discovery.batch_size}")
        
        # Concurrency config
        concurrency_node = config_tree.add("⚡ Concurrency")
        concurrency_node.add(f"Max Concurrent: {self.scanner.config.concurrency.max_concurrent}")
        concurrency_node.add(f"Batch Size: {self.scanner.config.concurrency.batch_size}")
        
        return Panel(
            config_tree,
            title="⚙️ Configuration",
            border_style="yellow"
        )
    
    def _create_controls_panel(self) -> Panel:
        """Create controls panel"""
        platform_note = "CMD/PowerShell" if sys.platform.startswith('win') else "Terminal"
        
        controls_text = Text.assemble(
            (f"Controls (focus {platform_note}): ", "bold white"),
            ("P", "cyan"), ("=Pause/Resume ", "white"),
            ("S", "cyan"), ("=Stop ", "white"),
            ("R", "cyan"), ("=Restart ", "white"),
            ("E", "cyan"), ("=Export ", "white"),
            ("Q", "cyan"), ("=Quit", "white")
        )
        
        return Panel(
            controls_text,
            title="⌨️ Controls",
            border_style="yellow"
        )
    
    def _update_display(self) -> None:
        """Update the display layout"""
        try:
            # Process keyboard input
            self._process_keyboard_input()
            
            # Update all panels
            self.layout["header"].update(self._create_header())
            self.layout["progress"].update(self._create_progress_panel())
            self.layout["stats"].update(self._create_stats_panel())
            self.layout["recent"].update(self._create_recent_servers_panel())
            self.layout["right"].update(self._create_config_panel())
            self.layout["footer"].update(self._create_controls_panel())
            
        except Exception as e:
            logger.error(f"Display update error: {e}")
    
    async def run(self, ip_range: str) -> None:
        """Run the console UI"""
        try:
            self._setup_terminal_input()
            
            # Start input handler thread
            self.input_thread = threading.Thread(target=self._input_handler_thread)
            self.input_thread.daemon = True
            self.input_thread.start()
            
            with Live(
                self.layout,
                console=self.console,
                refresh_per_second=self.scanner.config.ui.refresh_rate,
                screen=False,
                transient=False
            ) as live:
                
                # Start scanner in background
                scanner_task = asyncio.create_task(
                    self.scanner.scan_range(ip_range)
                )
                
                # Update display loop
                while self.running and not scanner_task.done():
                    self._update_display()
                    await asyncio.sleep(0.25)  # 4 FPS
                
                # Wait for scanner to complete
                if not scanner_task.done():
                    await scanner_task
                
                # Final update
                self._update_display()
                
                # Show completion message
                if not self.running:
                    self.console.print("\n[yellow]Scan interrupted by user[/yellow]")
                else:
                    self.console.print("\n[green]Scan completed successfully![/green]")
                    self.console.print("Press any key to exit...")
                    self._get_char_non_blocking()
        
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Interrupted by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]UI Error: {e}[/red]")
        finally:
            self._restore_terminal_input()
            self.running = False
            
            # Restore console logging
            self._restore_logging()
    
    def _restore_logging(self) -> None:
        """Restore console logging after UI exits"""
        root_logger = logging.getLogger()
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        root_logger.addHandler(console_handler)
    
    def add_server_found(self, server_data: Dict[str, Any]) -> None:
        """Add a found server to the recent list"""
        self.recent_servers.append(server_data)
        if len(self.recent_servers) > 50:  # Keep last 50
            self.recent_servers.pop(0) 