#!/usr/bin/env python3
"""
PingCrafty v0.2 - Modular Minecraft Server Scanner
Main entry point with CLI interface
"""

import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now use absolute imports
from core.scanner import MinecraftScanner
from core.config import ConfigManager
from core.exceptions import PingCraftyError
from ui.console import ConsoleUI
from ui.cli import CLIInterface

def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/pingcrafty.log'),
            logging.StreamHandler(sys.stdout) if verbose else logging.NullHandler()
        ]
    )

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    import signal
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(
        description="PingCrafty v0.2 - Modular Minecraft Server Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --range 192.168.1.0/24
  python main.py --range 10.0.0.0/16 --no-ui --verbose
  python main.py --file targets.txt --config custom_config.yaml
  python main.py --range 172.16.0.0/12 --export results.json
        """
    )
    
    # Utility commands (don't require target specification)
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration file and exit"
    )
    
    parser.add_argument(
        "--create-config",
        action="store_true",
        help="Create default configuration file and exit"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="PingCrafty v0.2.0"
    )
    
    # Configuration
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Configuration file path (default: config.yaml)"
    )
    
    # Target specification (only required for actual scanning)
    target_group = parser.add_mutually_exclusive_group(required=False)
    target_group.add_argument(
        "--range", "-r",
        help="IP range to scan (e.g., 192.168.1.0/24, 10.0.0.1-10.0.0.100)"
    )
    target_group.add_argument(
        "--file", "-f",
        help="File containing IP addresses or ranges to scan"
    )
    
    # UI options
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Run without interactive UI (headless mode)"
    )
    
    # Output options
    parser.add_argument(
        "--export",
        help="Export results to file (JSON, CSV, or Excel format)"
    )
    
    parser.add_argument(
        "--export-format",
        choices=['json', 'csv', 'xlsx'],
        help="Export format (auto-detected from file extension if not specified)"
    )
    
    # Scanning options
    parser.add_argument(
        "--ports", "-p",
        help="Comma-separated list of ports to scan (default: 25565)"
    )
    
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        help="Connection timeout in seconds"
    )
    
    parser.add_argument(
        "--rate-limit",
        type=int,
        help="Maximum requests per second"
    )
    
    parser.add_argument(
        "--max-concurrent",
        type=int,
        help="Maximum concurrent connections"
    )
    
    # Logging options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress all output except errors"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    if not args.quiet:
        setup_logging(args.verbose)
    
    # Setup signal handlers
    setup_signal_handlers()
    
    try:
        # Handle utility commands first
        if args.create_config:
            config_path = Path(args.config)
            if config_path.exists():
                response = input(f"Config file {config_path} already exists. Overwrite? (y/N): ")
                if response.lower() != 'y':
                    print("Aborted.")
                    return
            
            # Create the config manager which will create default config
            ConfigManager(args.config)
            print(f"✅ Default configuration created: {args.config}")
            return
        
        if args.validate_config:
            try:
                config = ConfigManager(args.config)
                print(f"✅ Configuration file {args.config} is valid")
                return
            except Exception as e:
                print(f"❌ Configuration validation failed: {e}")
                sys.exit(1)
        
        # For scanning commands, require target specification
        if not args.range and not args.file:
            parser.error("For scanning operations, one of --range/-r or --file/-f is required")
        
        # Load configuration
        config = ConfigManager(args.config)
        
        # Override configuration with command line arguments
        if args.ports:
            ports = [int(p.strip()) for p in args.ports.split(',')]
            config.discovery.ports = ports
        
        if args.timeout:
            config.scanner.timeout = args.timeout
        
        if args.rate_limit:
            config.scanner.rate_limit = args.rate_limit
        
        if args.max_concurrent:
            config.concurrency.max_concurrent = args.max_concurrent
        
        # Determine target specification
        target_spec = args.range or args.file
        
        # Initialize scanner
        scanner = MinecraftScanner(args.config)
        
        # Apply CLI overrides to scanner config
        scanner.config = config
        
        # Run scanner
        if args.no_ui or args.quiet:
            # Run CLI interface
            cli = CLIInterface(scanner)
            await cli.run(target_spec)
            
            # Handle export if requested
            if args.export:
                export_format = args.export_format
                if not export_format:
                    # Auto-detect format from file extension
                    ext = Path(args.export).suffix.lower()
                    if ext == '.json':
                        export_format = 'json'
                    elif ext == '.csv':
                        export_format = 'csv'
                    elif ext in ['.xlsx', '.xls']:
                        export_format = 'xlsx'
                    else:
                        export_format = 'json'  # Default
                
                await cli.export_data(export_format, args.export)
        else:
            # Run with interactive UI
            ui = ConsoleUI(scanner)
            await ui.run(target_spec)
            
    except KeyboardInterrupt:
        print("\n🛑 Scanning interrupted by user")
        sys.exit(0)
    except PingCraftyError as e:
        print(f"❌ PingCrafty error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Interrupted")
        sys.exit(0) 