"""
Enhanced Minecraft protocol handler with multi-protocol support
"""

import asyncio
import struct
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from .exceptions import ProtocolError
from .config_types import ScannerConfig

logger = logging.getLogger(__name__)

@dataclass
class ProtocolConfig:
    timeout: float = 5.0
    protocol_version: int = 770  # Single version mode
    protocol_versions: List[int] = field(default_factory=list)  # Multi-protocol mode
    scan_all_protocols: bool = False  # Enable multi-protocol scanning
    retries: int = 2
    legacy_support: bool = True
    
    @classmethod
    def from_scanner_config(cls, scanner_config: ScannerConfig) -> 'ProtocolConfig':
        """Create ProtocolConfig from ScannerConfig"""
        return cls(
            timeout=scanner_config.timeout,
            protocol_version=scanner_config.protocol_version,
            retries=scanner_config.retries,
            legacy_support=scanner_config.legacy_support
        )
    
    def __post_init__(self):
        # Initialize protocol_versions with default list if not provided
        if not self.protocol_versions:
            # Common Minecraft protocol versions
            self.protocol_versions = [
                # Modern versions (most common first for efficiency)
                770,  # 1.21
                767,  # 1.21
                766,  # 1.20.5-1.20.6
                765,  # 1.20.3-1.20.4
                764,  # 1.20.2
                763,  # 1.20-1.20.1
                762,  # 1.19.4
                761,  # 1.19.3
                760,  # 1.19.1-1.19.2
                759,  # 1.19
                758,  # 1.18.2
                757,  # 1.18-1.18.1
                756,  # 1.17.1
                755,  # 1.17
                754,  # 1.16.4-1.16.5
                753,  # 1.16.3
                751,  # 1.16.2
                736,  # 1.16.1
                735,  # 1.16
                578,  # 1.15.2
                575,  # 1.15.1
                573,  # 1.15
                498,  # 1.14.4
                490,  # 1.14.3
                485,  # 1.14.2
                480,  # 1.14.1
                477,  # 1.14
                404,  # 1.13.2
                401,  # 1.13.1
                393,  # 1.13
                340,  # 1.12.2
                338,  # 1.12.1
                335,  # 1.12
                316,  # 1.11.1-1.11.2
                315,  # 1.11
                210,  # 1.10.x
                109,  # 1.9.2-1.9.4
                108,  # 1.9.1
                107,  # 1.9
                47,   # 1.8.x
                5,    # 1.7.6-1.7.10
                4,    # 1.7.2-1.7.5
            ]

class MinecraftProtocol:
    """Enhanced Minecraft protocol handler with multi-protocol support"""
    
    # Packet constants
    HANDSHAKE_PACKET = 0x00
    STATUS_REQUEST_PACKET = 0x00
    PING_PACKET = 0x01
    
    # States
    STATE_STATUS = 1
    STATE_LOGIN = 2
    
    def __init__(self, config: ProtocolConfig):
        self.config = config
    
    async def ping_server(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """Ping a Minecraft server with protocol detection"""
        if self.config.scan_all_protocols:
            return await self._ping_with_protocol_detection(ip, port)
        else:
            return await self._ping_single_protocol(ip, port, self.config.protocol_version)
    
    async def _ping_with_protocol_detection(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """Try multiple protocol versions to find the best match"""
        
        # First, try a quick ping with the most common modern protocol
        result = await self._ping_single_protocol(ip, port, 770)
        if result:
            result['detected_protocol'] = 770
            return result
        
        # If that fails, try other protocols in order of commonality
        for protocol_version in self.config.protocol_versions:
            try:
                result = await self._ping_single_protocol(ip, port, protocol_version)
                if result:
                    result['detected_protocol'] = protocol_version
                    result['protocol_detection_used'] = True
                    logger.debug(f"Successfully connected to {ip}:{port} using protocol {protocol_version}")
                    return result
            except Exception as e:
                logger.debug(f"Protocol {protocol_version} failed for {ip}:{port}: {e}")
                continue
        
        # Try legacy ping as last resort
        if self.config.legacy_support:
            result = await self._legacy_ping(ip, port)
            if result:
                result['detected_protocol'] = 'legacy'
                result['protocol_detection_used'] = True
                return result
        
        return None
    
    async def _ping_single_protocol(self, ip: str, port: int, protocol_version: int) -> Optional[Dict[str, Any]]:
        """Ping server with a specific protocol version"""
        for attempt in range(self.config.retries + 1):
            try:
                result = await self._modern_ping(ip, port, protocol_version)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"Ping attempt {attempt + 1} failed for {ip}:{port} (protocol {protocol_version}): {e}")
                if attempt < self.config.retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
        
        return None
    
    async def _modern_ping(self, ip: str, port: int, protocol_version: int) -> Optional[Dict[str, Any]]:
        """Modern Minecraft server ping with specific protocol version"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=self.config.timeout
            )
            
            try:
                # Send handshake packet with specific protocol version
                handshake = self._create_handshake_packet(ip, port, protocol_version)
                writer.write(handshake)
                
                # Send status request
                status_request = self._create_packet(self.STATUS_REQUEST_PACKET, b'')
                writer.write(status_request)
                await writer.drain()
                
                # Read response
                response_data = await self._read_packet(reader)
                if response_data:
                    json_str = response_data.decode('utf-8', errors='ignore')
                    result = json.loads(json_str)
                    
                    # Add the protocol version used for this successful ping
                    result['ping_protocol_used'] = protocol_version
                    return result
                
                return None
                
            finally:
                writer.close()
                await writer.wait_closed()
                
        except Exception as e:
            logger.debug(f"Modern ping failed for {ip}:{port} (protocol {protocol_version}): {e}")
            return None
    
    def _create_handshake_packet(self, ip: str, port: int, protocol_version: int) -> bytes:
        """Create handshake packet with specific protocol version"""
        # Encode server address
        addr_bytes = ip.encode('utf-8')
        addr_len = self._encode_varint(len(addr_bytes))
        
        # Encode protocol version (use the specified version)
        protocol = self._encode_varint(protocol_version)
        
        # Encode port
        port_bytes = struct.pack('>H', port)
        
        # Encode next state (status)
        next_state = self._encode_varint(self.STATE_STATUS)
        
        # Combine data
        data = protocol + addr_len + addr_bytes + port_bytes + next_state
        
        # Create packet
        return self._create_packet(self.HANDSHAKE_PACKET, data)
    
    def _create_packet(self, packet_id: int, data: bytes) -> bytes:
        """Create a packet with ID and data"""
        packet_id_bytes = self._encode_varint(packet_id)
        packet_data = packet_id_bytes + data
        packet_length = self._encode_varint(len(packet_data))
        return packet_length + packet_data
    
    async def _read_packet(self, reader: asyncio.StreamReader) -> Optional[bytes]:
        """Read a packet from the stream"""
        try:
            # Read packet length
            length = 0
            shift = 0
            
            while True:
                byte = await reader.read(1)
                if not byte:
                    return None
                
                value = byte[0]
                length |= (value & 0x7F) << shift
                
                if not (value & 0x80):
                    break
                    
                shift += 7
                if shift > 35:
                    raise ProtocolError("VarInt too big")
            
            # Read packet data
            data = await reader.read(length)
            if not data:
                return None
            
            # Skip packet ID for status response
            pos = 0
            while pos < len(data):
                value = data[pos]
                pos += 1
                if not (value & 0x80):
                    break
            
            return data[pos:]
            
        except Exception as e:
            logger.debug(f"Error reading packet: {e}")
            return None
    
    def _encode_varint(self, value: int) -> bytes:
        """Encode an integer as a VarInt"""
        result = bytearray()
        while True:
            byte = value & 0x7F
            value >>= 7
            if value:
                byte |= 0x80
            result.append(byte)
            if not value:
                break
        return bytes(result)
    
    async def _legacy_ping(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """Legacy Minecraft server ping (Beta 1.8+)"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=self.config.timeout
            )
            
            try:
                # Send legacy ping (0xFE packet)
                legacy_ping = b'\xfe\x01\xfa\x00\x0b\x00M\x00C\x00|\x00P\x00i\x00n\x00g\x00H\x00o\x00s\x00t\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                writer.write(legacy_ping)
                await writer.drain()
                
                # Read response
                response = await reader.read(1024)
                if response and len(response) > 1:
                    result = self._parse_legacy_response(response)
                    if result:
                        result['legacy'] = True
                        result['ping_protocol_used'] = 'legacy'
                    return result
                
                return None
                
            finally:
                writer.close()
                await writer.wait_closed()
                
        except Exception as e:
            logger.debug(f"Legacy ping failed for {ip}:{port}: {e}")
            return None
    
    def _parse_legacy_response(self, response: bytes) -> Optional[Dict[str, Any]]:
        """Parse legacy server response"""
        try:
            if response[0] == 0xFF:  # Kick packet
                # Skip packet ID and length
                data = response[3:].decode('utf-16-be')
                parts = data.split('\u0000')
                
                if len(parts) >= 6:
                    return {
                        'version': {
                            'name': parts[2],
                            'protocol': -1  # Legacy protocol
                        },
                        'players': {
                            'online': int(parts[4]),
                            'max': int(parts[5])
                        },
                        'description': {
                            'text': parts[3]
                        },
                        'legacy_response': True
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error parsing legacy response: {e}")
            return None 