# PingCrafty v0.2

A high-performance, modular Minecraft server scanner with advanced features including real-time UI, database storage, geolocation, and comprehensive server information extraction.

## 🌟 Features

### Core Scanning
- **High-Performance Scanning**: Asynchronous scanning with configurable concurrency
- **Protocol Support**: Modern Minecraft protocol (1.7+) with legacy server support
- **Multiple Discovery Methods**: IP ranges, Masscan integration, and file input
- **Smart Rate Limiting**: Configurable rate limiting with burst support

### Data Collection
- **Comprehensive Server Info**: Version, software, MOTD, player count, mods, and more
- **Player Tracking**: Track players across servers with UUID support
- **Mod Detection**: Comprehensive mod and plugin detection (Forge, Fabric, Bukkit, etc.)
- **Server Classification**: Automatic server software type detection

### Advanced Features
- **Real-time UI**: Rich console interface with live progress updates
- **Database Storage**: SQLite and PostgreSQL support with advanced schema
- **Geolocation**: GeoIP2 integration with ISP detection
- **IP Blacklisting**: Advanced blacklist management with network range support
- **Memory Management**: Intelligent memory monitoring and cleanup
- **Export Options**: JSON, CSV, and Excel export with filtering

### Integrations
- **Webhook Support**: Discord, Slack, and custom webhook notifications
- **Masscan Integration**: High-speed port discovery using Masscan
- **Modular Architecture**: Plugin system for extending functionality

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/pingcrafty-v2.git
cd pingcrafty-v2

# Install dependencies
pip install -r requirements.txt

# Create default configuration
python main.py --create-config

# Run a basic scan
python main.py --range 192.168.1.0/24
```

### Basic Usage

```bash
# Scan an IP range with interactive UI
python main.py --range 10.0.0.0/16

# Headless scanning with export
python main.py --range 172.16.0.0/12 --no-ui --export results.json

# Scan from file with custom ports
python main.py --file targets.txt --ports 25565,25566,25567

# High-performance scanning
python main.py --range 192.168.0.0/16 --max-concurrent 2000 --rate-limit 5000
```

## 📋 Configuration

PingCrafty v0.2 uses a comprehensive YAML configuration file. Create a default configuration:

```bash
python main.py --create-config
```

Key configuration sections:
- **Scanner**: Protocol settings, timeouts, retries
- **Discovery**: Target generation methods and ports
- **Concurrency**: Performance and connection limits
- **Database**: Storage backend configuration
- **Modules**: Blacklist, geolocation, webhooks
- **UI**: Interface settings and preferences

## 🗃️ Database Schema

PingCrafty v0.2 features an enhanced database schema:

### Core Tables
- `servers`: Main server registry with availability tracking
- `server_status`: Historical server status snapshots
- `players`: Player information with UUID tracking
- `player_sessions`: Player presence across servers

### Enhanced Features
- `mods`: Comprehensive mod and plugin tracking
- `server_mods`: Server-to-mod associations
- `favicons`: Deduplicated favicon storage
- `server_locations`: GeoIP and ISP data
- `ip_blacklist`: Advanced blacklist management

## 🎛️ Command Line Interface

### Target Specification
```bash
# IP ranges
--range 192.168.1.0/24
--range 10.0.0.1-10.0.0.100

# File input
--file targets.txt
```

### Scanning Options
```bash
--ports 25565,25566,25567    # Custom ports
--timeout 10                 # Connection timeout
--rate-limit 2000           # Requests per second
--max-concurrent 1500       # Concurrent connections
```

### Output Options
```bash
--no-ui                     # Headless mode
--export results.json       # Export results
--export-format csv         # Export format
--verbose                   # Detailed logging
--quiet                     # Minimal output
```

### Utility Commands
```bash
--validate-config           # Validate configuration
--create-config            # Create default config
--version                  # Show version
```

## 🧩 Modular Architecture

PingCrafty v0.2 features a modular, plugin-based architecture:

### Core Modules
- **scanner**: Main scanning engine
- **protocol**: Minecraft protocol handling
- **database**: Multi-backend database support
- **config**: Configuration management

### Feature Modules
- **discovery**: Target generation (range, masscan, file)
- **geolocation**: GeoIP and ISP detection
- **blacklist**: IP filtering and management
- **webhook**: Notification integrations

### Utility Modules
- **concurrency**: Connection pooling and rate limiting
- **memory**: Memory monitoring and optimization
- **export**: Data export in multiple formats
- **network**: Network utilities and helpers

### UI Modules
- **console**: Rich interactive console interface
- **cli**: Command-line interface for automation

## 📊 Export Formats

### JSON Export
```json
{
  "export_info": {
    "timestamp": "2023-08-15T10:30:00Z",
    "total_records": 1500,
    "format": "json"
  },
  "servers": [
    {
      "ip": "192.168.1.100",
      "port": 25565,
      "version": "1.20.1",
      "software": "paper",
      "online_mode": "offline",
      "players": {"online": 15, "max": 100},
      "location": {"country": "US", "city": "New York"}
    }
  ]
}
```

### CSV Export
Structured tabular data with server information, perfect for analysis in spreadsheet applications.

### Excel Export
Multi-sheet workbook with:
- **Servers**: Main server data
- **Summary**: Statistics and analysis
- **Players**: Player information
- **Mods**: Detected modifications

## 🔧 Advanced Configuration

### Database Backends

#### SQLite (Default)
```yaml
database:
  type: "sqlite"
  path: "servers.db"
```

#### PostgreSQL
```yaml
database:
  type: "postgresql"
  host: "localhost"
  port: 5432
  database: "pingcrafty"
  user: "postgres"
  password: "your_password"
  pool_size: 20
```

### Geolocation Setup

1. Download GeoLite2 database from MaxMind
2. Configure path in config.yaml:
```yaml
geolocation:
  enabled: true
  provider: "geoip2"
  database_path: "GeoLite2-City.mmdb"
```

### Webhook Integration

#### Discord Webhook
```yaml
webhook:
  enabled: true
  url: "https://discord.com/api/webhooks/..."
  batch_size: 50
  include_stats: true
```

### Masscan Integration

1. Install Masscan
2. Configure discovery method:
```yaml
discovery:
  method: "masscan"
  masscan_rate: 10000
  masscan_excludes: "exclude.conf"
```

## 🛠️ Development

### Project Structure
```
pingcrafty-v2/
├── core/                   # Core engine
│   ├── scanner.py         # Main scanner
│   ├── protocol.py        # Minecraft protocol
│   ├── database.py        # Database management
│   └── config.py          # Configuration
├── modules/               # Feature modules
│   ├── discovery.py       # Target discovery
│   ├── geolocation.py     # GeoIP integration
│   ├── blacklist.py       # IP blacklisting
│   └── webhook.py         # Notifications
├── parsers/               # Data parsers
│   └── server_parser.py   # Server response parsing
├── ui/                    # User interfaces
│   ├── console.py         # Rich console UI
│   └── cli.py             # Command-line interface
├── utils/                 # Utilities
│   ├── concurrency.py     # Connection management
│   ├── memory.py          # Memory optimization
│   ├── export.py          # Data export
│   └── network.py         # Network utilities
├── main.py                # Entry point
├── config.yaml           # Configuration
└── requirements.txt       # Dependencies
```

### Adding Custom Modules

Create a new module by extending `ScannerModule`:

```python
from core.scanner import ScannerModule, ScanResult

class CustomModule(ScannerModule):
    async def initialize(self, scanner):
        # Initialize your module
        pass
    
    async def process_result(self, result: ScanResult):
        # Process scan results
        pass
    
    async def finalize(self):
        # Cleanup
        pass
    
# Add to scanner
scanner.add_module(CustomModule())
```

## 📚 User & Developer Documentation

### Usage Example

Run a basic scan on a local network:

```bash
python main.py --range 192.168.1.0/24
```

Export results to CSV:

```bash
python main.py --range 10.0.0.0/16 --no-ui --export results.csv --export-format csv
```

Validate your configuration:

```bash
python -m ui.cli --validate-config --config config.yaml
```

Create a default configuration:

```bash
python -m ui.cli --create-config --config config.yaml
```

### Module/Plugin Guide

PingCrafty supports easy extension via modules. To add a custom module:

1. **Create your module:**

```python
from core.scanner import ScannerModule, ScanResult

class MyCustomModule(ScannerModule):
    async def initialize(self, scanner):
        # Setup logic
        pass
    async def process_result(self, result: ScanResult):
        # Handle each scan result
        print(f"Found server: {result.ip}:{result.port}")
    async def finalize(self):
        # Cleanup logic
        pass
```

2. **Register your module with the scanner:**

```python
scanner = MinecraftScanner()
scanner.add_module(MyCustomModule())
```

3. **Run the scanner as usual.**

See the `core/scanner.py` and this README for more details.

---

## 📈 Performance

### Benchmarks
- **Scan Rate**: Up to 10,000+ IPs/second (hardware dependent)
- **Memory Usage**: Optimized with intelligent cleanup
- **Database**: Efficient storage with proper indexing
- **Concurrency**: Configurable limits for optimal performance

### Optimization Tips
1. **Increase Concurrency**: Adjust `max_concurrent` for faster scanning
2. **Database Tuning**: Use PostgreSQL for large-scale deployments
3. **Memory Management**: Configure appropriate memory limits
4. **Rate Limiting**: Balance speed with target server protection

## 🔒 Security Considerations

- **Rate Limiting**: Configurable to prevent overwhelming targets
- **Blacklist Support**: Comprehensive IP filtering
- **Responsible Scanning**: Built-in delays and limits
- **Data Protection**: Secure storage of collected information

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

- **Documentation**: [Wiki](https://github.com/your-org/pingcrafty-v2/wiki)
- **Issues**: [GitHub Issues](https://github.com/your-org/pingcrafty-v2/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/pingcrafty-v2/discussions)

## 🙏 Acknowledgments

- Inspired by ServerSeekerV2 and other Minecraft scanning tools
- Thanks to the Minecraft community for protocol documentation
- Built with modern Python async/await patterns

---

**PingCrafty v0.2** - Modular. Powerful. Efficient. 