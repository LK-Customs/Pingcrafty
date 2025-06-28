"""
Enhanced server response parser inspired by ServerSeekerV2
"""

import json
import re
import logging
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from core.exceptions import ParsingError

logger = logging.getLogger(__name__)

class ServerType(Enum):
    """Server software types"""
    VANILLA = "vanilla"
    PAPER = "paper"
    SPIGOT = "spigot"
    BUKKIT = "bukkit"
    PURPUR = "purpur"
    FOLIA = "folia"
    PUFFERFISH = "pufferfish"
    FORGE = "forge"
    NEOFORGE = "neoforge"
    FABRIC = "fabric"
    QUILT = "quilt"
    VELOCITY = "velocity"
    BUNGEECORD = "bungeecord"
    WATERFALL = "waterfall"
    UNKNOWN = "unknown"

@dataclass
class ParsedServer:
    """Parsed server data"""
    ip: str = ""
    port: int = 25565
    version_name: str = "Unknown"
    protocol_version: int = -1
    server_type: ServerType = ServerType.UNKNOWN
    motd_raw: Optional[str] = None
    motd_formatted: Optional[str] = None
    favicon: Optional[str] = None
    favicon_hash: Optional[str] = None
    online_players: int = 0
    max_players: int = 0
    player_sample: List[Dict[str, str]] = field(default_factory=list)
    mods: List[Dict[str, str]] = field(default_factory=list)
    enforces_secure_chat: Optional[bool] = None
    prevents_chat_reports: Optional[bool] = None
    online_mode: str = "unknown"
    
    def __post_init__(self):
        if self.player_sample is None:
            self.player_sample = []
        if self.mods is None:
            self.mods = []

class MOTDParser:
    """MOTD parsing with Minecraft formatting"""
    
    COLOR_CODES = {
        'black': '0', 'dark_blue': '1', 'dark_green': '2', 'dark_aqua': '3',
        'dark_red': '4', 'dark_purple': '5', 'purple': '5', 'gold': '6',
        'gray': '7', 'grey': '7', 'dark_gray': '8', 'dark_grey': '8',
        'blue': '9', 'green': 'a', 'aqua': 'b', 'red': 'c',
        'light_purple': 'd', 'pink': 'd', 'yellow': 'e', 'white': 'f',
        'reset': 'r'
    }
    
    FORMATTING_CODES = {
        'bold': 'l', 'italic': 'o', 'underlined': 'n', 
        'strikethrough': 'm', 'obfuscated': 'k'
    }
    
    @classmethod
    def parse_motd(cls, description: Any) -> tuple[Optional[str], Optional[str]]:
        """Parse MOTD from server response"""
        if not description:
            return None, None
        
        try:
            if isinstance(description, str):
                raw = description
                formatted = cls._clean_formatting(description)
            elif isinstance(description, dict):
                raw = json.dumps(description, separators=(',', ':'))
                formatted = cls._build_formatted_text(description)
            elif isinstance(description, list):
                raw = json.dumps(description, separators=(',', ':'))
                formatted = cls._build_formatted_text({'extra': description})
            else:
                raw = str(description)
                formatted = cls._clean_formatting(str(description))
            
            return raw, formatted
            
        except Exception as e:
            logger.debug(f"MOTD parsing error: {e}")
            return str(description)[:500] if description else None, None
    
    @classmethod
    def _build_formatted_text(cls, obj: Any, depth: int = 0) -> str:
        """Build formatted text from JSON description"""
        if depth > 10:  # Prevent infinite recursion
            return ""
        
        if isinstance(obj, str):
            return obj
        elif isinstance(obj, list):
            return ''.join(cls._build_formatted_text(item, depth + 1) for item in obj)
        elif isinstance(obj, dict):
            output = ""
            
            # Apply formatting codes
            for format_name, code in cls.FORMATTING_CODES.items():
                if obj.get(format_name):
                    output += f'§{code}'
            
            # Apply color
            if 'color' in obj:
                color = obj['color']
                if color in cls.COLOR_CODES:
                    output += f"§{cls.COLOR_CODES[color]}"
                elif color.startswith('#') and len(color) == 7:
                    # Hex color - convert to nearest legacy color
                    output += cls._hex_to_legacy_color(color)
            
            # Add text content
            if 'text' in obj:
                output += str(obj['text'])
            
            # Process extra content
            if 'extra' in obj and isinstance(obj['extra'], list):
                output += cls._build_formatted_text(obj['extra'], depth + 1)
            
            # Process with content (alternative format)
            if 'with' in obj and isinstance(obj['with'], list):
                output += cls._build_formatted_text(obj['with'], depth + 1)
            
            return output
        
        return str(obj)
    
    @classmethod
    def _hex_to_legacy_color(cls, hex_color: str) -> str:
        """Convert hex color to nearest legacy color code"""
        try:
            # Remove # and convert to RGB
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Find nearest legacy color (simplified mapping)
            if r > 200 and g > 200 and b > 200:
                return '§f'  # white
            elif r < 50 and g < 50 and b < 50:
                return '§0'  # black
            elif r > g and r > b:
                return '§c' if r > 150 else '§4'  # red/dark_red
            elif g > r and g > b:
                return '§a' if g > 150 else '§2'  # green/dark_green
            elif b > r and b > g:
                return '§9' if b > 150 else '§1'  # blue/dark_blue
            else:
                return '§7'  # gray
                
        except (ValueError, IndexError):
            return '§r'  # reset
    
    @classmethod
    def _clean_formatting(cls, text: str) -> str:
        """Clean formatting codes from text"""
        if not text:
            return ""
        
        # Remove §X color codes
        text = re.sub(r'§[0-9a-fk-or]', '', text)
        # Remove &X codes
        text = re.sub(r'&[0-9a-fk-or]', '', text)
        # Remove JSON color codes
        text = re.sub(r'\{"color":"[^"]*"\}', '', text)
        # Clean excessive whitespace
        text = ' '.join(text.split())
        
        return text.strip()

class ServerResponseParser:
    """Enhanced server response parser"""
    
    def __init__(self):
        self.motd_parser = MOTDParser()
    
    async def parse_response(self, response_data: Dict[str, Any]) -> ParsedServer:
        """Parse server response into structured data"""
        try:
            # Create base parsed server object
            parsed = ParsedServer()
            
            # Extract version information
            version_info = response_data.get('version', {})
            if isinstance(version_info, dict):
                parsed.version_name = version_info.get('name', 'Unknown')
                parsed.protocol_version = version_info.get('protocol', -1)
            
            # Detect server type
            parsed.server_type = self._detect_server_type(response_data, parsed.version_name)
            
            # Parse MOTD
            parsed.motd_raw, parsed.motd_formatted = self.motd_parser.parse_motd(
                response_data.get('description')
            )
            
            # Extract player information
            players_info = response_data.get('players', {})
            if isinstance(players_info, dict):
                parsed.online_players = players_info.get('online', 0)
                parsed.max_players = players_info.get('max', 0)
                
                # Extract player sample
                sample = players_info.get('sample', [])
                if isinstance(sample, list):
                    for player in sample:
                        if isinstance(player, dict) and 'id' in player and 'name' in player:
                            parsed.player_sample.append({
                                'uuid': player['id'].replace('-', ''),
                                'name': player['name']
                            })
            
            # Extract mods
            parsed.mods = self._extract_mods(response_data)
            
            # Extract additional properties
            parsed.enforces_secure_chat = response_data.get('enforcesSecureChat')
            parsed.prevents_chat_reports = response_data.get('preventsChatReports')
            
            # Extract and process favicon
            favicon = response_data.get('favicon')
            if favicon:
                parsed.favicon = favicon
                parsed.favicon_hash = hashlib.md5(favicon.encode()).hexdigest()
            
            # Determine online mode (this would typically require additional probing)
            parsed.online_mode = self._determine_online_mode(response_data)
            
            return parsed
            
        except Exception as e:
            logger.error(f"Failed to parse server response: {e}")
            raise ParsingError(f"Server response parsing failed: {e}")
    
    def _detect_server_type(self, response_data: Dict[str, Any], version_name: str) -> ServerType:
        """Detect server software type"""
        try:
            # Check for explicit server type indicators in response
            if response_data.get('isModded') or response_data.get('modded'):
                return ServerType.NEOFORGE
            
            if 'forgeData' in response_data or 'modinfo' in response_data:
                return ServerType.FORGE
            
            # Check version string for server type indicators
            version_lower = version_name.lower() if version_name else ""
            
            # Paper-based servers
            if 'paper' in version_lower:
                if 'purpur' in version_lower:
                    return ServerType.PURPUR
                elif 'folia' in version_lower:
                    return ServerType.FOLIA
                elif 'pufferfish' in version_lower:
                    return ServerType.PUFFERFISH
                else:
                    return ServerType.PAPER
            
            # Other Bukkit-based servers
            elif 'spigot' in version_lower:
                return ServerType.SPIGOT
            elif 'bukkit' in version_lower or 'craftbukkit' in version_lower:
                return ServerType.BUKKIT
            
            # Modded servers
            elif 'forge' in version_lower or 'fml' in version_lower:
                if 'neoforge' in version_lower:
                    return ServerType.NEOFORGE
                else:
                    return ServerType.FORGE
            elif 'fabric' in version_lower:
                return ServerType.FABRIC
            elif 'quilt' in version_lower:
                return ServerType.QUILT
            
            # Proxy servers
            elif 'velocity' in version_lower:
                return ServerType.VELOCITY
            elif 'bungeecord' in version_lower:
                return ServerType.BUNGEECORD
            elif 'waterfall' in version_lower:
                return ServerType.WATERFALL
            
            # Check MOTD for additional indicators
            motd_text = ""
            if 'description' in response_data:
                _, motd_text = self.motd_parser.parse_motd(response_data['description'])
                motd_text = (motd_text or "").lower()
            
            # MOTD-based detection
            if motd_text:
                if any(indicator in motd_text for indicator in ['paper', 'purpur', 'folia']):
                    return ServerType.PAPER
                elif any(indicator in motd_text for indicator in ['spigot', 'bukkit']):
                    return ServerType.SPIGOT
                elif any(indicator in motd_text for indicator in ['forge', 'modded', 'mods']):
                    return ServerType.FORGE
                elif any(indicator in motd_text for indicator in ['fabric', 'quilt']):
                    return ServerType.FABRIC
            
            # Check for vanilla indicators
            if re.search(r'minecraft server|vanilla', version_lower):
                return ServerType.VANILLA
            
            # If version looks like a standard MC version, assume vanilla
            if re.match(r'^1\.\d+(\.\d+)?$', version_name or ""):
                return ServerType.VANILLA
            
            return ServerType.UNKNOWN
            
        except Exception as e:
            logger.debug(f"Server type detection error: {e}")
            return ServerType.UNKNOWN
    
    def _extract_mods(self, response_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract mod information from server response"""
        mods = []
        
        try:
            # Check for Forge mod data
            forge_data = response_data.get('forgeData') or response_data.get('modinfo')
            if forge_data and isinstance(forge_data, dict):
                mod_list = forge_data.get('mods') or forge_data.get('modList', [])
                if isinstance(mod_list, list):
                    for mod in mod_list:
                        if isinstance(mod, dict):
                            mod_info = {
                                'id': mod.get('modId') or mod.get('modid', ''),
                                'version': mod.get('version') or mod.get('modmarker', ''),
                                'type': 'forge'
                            }
                            if mod_info['id']:
                                mods.append(mod_info)
            
            # Check for Fabric mods (if present in response)
            if 'fabricMods' in response_data:
                fabric_mods = response_data['fabricMods']
                if isinstance(fabric_mods, list):
                    for mod in fabric_mods:
                        if isinstance(mod, dict):
                            mod_info = {
                                'id': mod.get('id', ''),
                                'version': mod.get('version', ''),
                                'type': 'fabric'
                            }
                            if mod_info['id']:
                                mods.append(mod_info)
            
            # Check for NeoForge mods
            if 'neoForgeData' in response_data:
                neo_mods = response_data['neoForgeData'].get('mods', [])
                if isinstance(neo_mods, list):
                    for mod in neo_mods:
                        if isinstance(mod, dict):
                            mod_info = {
                                'id': mod.get('modId', ''),
                                'version': mod.get('version', ''),
                                'type': 'neoforge'
                            }
                            if mod_info['id']:
                                mods.append(mod_info)
            
            # Check for plugins in response (some servers expose this)
            if 'plugins' in response_data:
                plugins = response_data['plugins']
                if isinstance(plugins, list):
                    for plugin in plugins:
                        if isinstance(plugin, dict):
                            mod_info = {
                                'id': plugin.get('name', ''),
                                'version': plugin.get('version', ''),
                                'type': 'plugin'
                            }
                            if mod_info['id']:
                                mods.append(mod_info)
        
        except Exception as e:
            logger.debug(f"Mod extraction error: {e}")
        
        return mods
    
    def _determine_online_mode(self, response_data: Dict[str, Any]) -> str:
        """Determine if server is in online mode"""
        try:
            # Some servers explicitly report this
            if 'onlineMode' in response_data:
                return 'online' if response_data['onlineMode'] else 'offline'
            
            # Check for enforced secure chat (usually indicates online mode)
            if response_data.get('enforcesSecureChat'):
                return 'online'
            
            # Check if chat reports are prevented (often indicates offline mode)
            if response_data.get('preventsChatReports'):
                return 'offline'
            
            # Look for cracked/offline indicators in MOTD
            motd_text = ""
            if 'description' in response_data:
                _, motd_text = self.motd_parser.parse_motd(response_data['description'])
                motd_text = (motd_text or "").lower()
            
            offline_indicators = [
                'cracked', 'offline', 'no premium', 'no-premium', 
                'pirate', 'tlauncher', 'free', 'non-premium'
            ]
            
            if any(indicator in motd_text for indicator in offline_indicators):
                return 'offline'
            
            # Default to unknown if we can't determine
            return 'unknown'
            
        except Exception as e:
            logger.debug(f"Online mode detection error: {e}")
            return 'unknown'
    
    def clean_json_string(self, json_string: str) -> Optional[str]:
        """Clean malformed JSON strings"""
        try:
            # Find the start and end of JSON
            start = json_string.find('{')
            if start == -1:
                return None
            
            # Find the matching closing brace
            brace_count = 0
            end = start
            for i, char in enumerate(json_string[start:], start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
            
            if brace_count == 0:
                return json_string[start:end]
            return None
            
        except Exception:
            return None
    
    def extract_version_pattern(self, text: str, pattern: str) -> Optional[str]:
        """Extract version using regex pattern"""
        try:
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(1) if match else None
        except Exception:
            return None 