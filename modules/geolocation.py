"""
Geolocation and ISP detection module
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod

try:
    import geoip2.database
    import geoip2.errors
    GEOIP2_AVAILABLE = True
except ImportError:
    GEOIP2_AVAILABLE = False

try:
    from ipwhois import IPWhois
    IPWHOIS_AVAILABLE = True
except ImportError:
    IPWHOIS_AVAILABLE = False

from core.exceptions import GeolocationError

logger = logging.getLogger(__name__)

@dataclass
class LocationData:
    """Container for location information"""
    ip: str
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    isp: Optional[str] = None
    asn: Optional[int] = None
    asn_description: Optional[str] = None

class GeolocationProvider(ABC):
    """Base class for geolocation providers"""
    
    @abstractmethod
    async def get_location(self, ip: str) -> Optional[LocationData]:
        """Get location data for an IP address"""
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Cleanup resources"""
        pass

class GeoIP2Provider(GeolocationProvider):
    """GeoIP2 database provider"""
    
    def __init__(self, database_path: str):
        self.database_path = database_path
        self.reader = None
        
    async def initialize(self) -> None:
        """Initialize GeoIP2 database"""
        if not GEOIP2_AVAILABLE:
            raise GeolocationError("geoip2 library not available")
        
        try:
            self.reader = geoip2.database.Reader(self.database_path)
            logger.info(f"GeoIP2 database loaded: {self.database_path}")
        except Exception as e:
            raise GeolocationError(f"Failed to load GeoIP2 database: {e}")
    
    async def get_location(self, ip: str) -> Optional[LocationData]:
        """Get location data from GeoIP2"""
        if not self.reader:
            return None
        
        try:
            response = self.reader.city(ip)
            
            return LocationData(
                ip=ip,
                country_code=response.country.iso_code,
                country_name=response.country.name,
                region=response.subdivisions.most_specific.name if response.subdivisions else None,
                city=response.city.name,
                latitude=float(response.location.latitude) if response.location.latitude else None,
                longitude=float(response.location.longitude) if response.location.longitude else None
            )
        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"No GeoIP2 data found for {ip}")
            return None
        except Exception as e:
            logger.debug(f"GeoIP2 error for {ip}: {e}")
            return None
    
    async def close(self) -> None:
        """Close GeoIP2 database"""
        if self.reader:
            self.reader.close()

class IPAPIProvider(GeolocationProvider):
    """IP-API.com provider (requires internet connection)"""
    
    def __init__(self):
        self.session = None
        self.rate_limit_delay = 1.0  # 1 second between requests
        self.last_request_time = 0
        
    async def initialize(self) -> None:
        """Initialize HTTP session"""
        try:
            import aiohttp
            self.session = aiohttp.ClientSession()
            logger.info("IP-API provider initialized")
        except ImportError:
            raise GeolocationError("aiohttp required for IP-API provider")
    
    async def get_location(self, ip: str) -> Optional[LocationData]:
        """Get location data from IP-API"""
        if not self.session:
            return None
        
        # Rate limiting
        now = time.time()
        if now - self.last_request_time < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - (now - self.last_request_time))
        
        try:
            url = f"http://ip-api.com/json/{ip}"
            async with self.session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'success':
                        asn = None
                        if data.get('as'):
                            try:
                                asn = int(data['as'].split()[0][2:])
                            except (ValueError, IndexError):
                                pass
                                
                        return LocationData(
                            ip=ip,
                            country_code=data.get('countryCode'),
                            country_name=data.get('country'),
                            region=data.get('regionName'),
                            city=data.get('city'),
                            latitude=data.get('lat'),
                            longitude=data.get('lon'),
                            isp=data.get('isp'),
                            asn=asn
                        )
            
            self.last_request_time = time.time()
            return None
            
        except Exception as e:
            logger.debug(f"IP-API error for {ip}: {e}")
            return None
    
    async def close(self) -> None:
        """Close HTTP session"""
        if self.session:
            await self.session.close()

class WhoisProvider:
    """WHOIS/ASN data provider"""
    
    def __init__(self):
        self.cache: Dict[str, tuple[Dict[str, Any], float]] = {}
        self.cache_duration = 3600  # 1 hour
    
    async def get_asn_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get ASN information for an IP"""
        if not IPWHOIS_AVAILABLE:
            return None
        
        # Check cache
        cache_key = ip
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_duration:
                return cached_data
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            whois_data = await loop.run_in_executor(
                None, 
                self._get_whois_data, 
                ip
            )
            
            if whois_data:
                # Cache the result
                self.cache[cache_key] = (whois_data, time.time())
                return whois_data
            
            return None
            
        except Exception as e:
            logger.debug(f"WHOIS error for {ip}: {e}")
            return None
    
    def _get_whois_data(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get WHOIS data (blocking operation)"""
        try:
            whois = IPWhois(ip, timeout=5)
            result = whois.lookup_rdap(depth=1)
            
            return {
                'asn': result.get('asn'),
                'asn_description': result.get('asn_description'),
                'network_name': result.get('network', {}).get('name'),
                'network_country': result.get('network', {}).get('country')
            }
        except Exception:
            return None

class GeolocationManager:
    """Main geolocation manager"""
    
    def __init__(self, config):
        self.config = config
        self.enabled = config.enabled
        self.cache: Dict[str, tuple[LocationData, float]] = {}
        self.cache_duration = config.cache_duration
        
        # Initialize providers
        self.geo_provider = None
        self.whois_provider = WhoisProvider() if IPWHOIS_AVAILABLE else None
        
    async def initialize(self) -> None:
        """Initialize geolocation providers"""
        if not self.enabled:
            logger.info("Geolocation disabled")
            return
        
        # Initialize main geolocation provider
        if self.config.provider == "geoip2":
            self.geo_provider = GeoIP2Provider(self.config.database_path)
        elif self.config.provider == "ipapi":
            self.geo_provider = IPAPIProvider()
        else:
            raise GeolocationError(f"Unknown geolocation provider: {self.config.provider}")
        
        await self.geo_provider.initialize()
        logger.info(f"Geolocation manager initialized with {self.config.provider} provider")
    
    async def get_location_data(self, ip: str) -> Optional[LocationData]:
        """Get comprehensive location data for an IP"""
        if not self.enabled or not self.geo_provider:
            return None
        
        # Check cache first
        cache_key = ip
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_duration:
                return cached_data
        
        try:
            # Get basic location data
            location_data = await self.geo_provider.get_location(ip)
            if not location_data:
                return None
            
            # Enhance with WHOIS/ASN data if available
            if self.whois_provider:
                asn_data = await self.whois_provider.get_asn_info(ip)
                if asn_data:
                    location_data.asn = asn_data.get('asn')
                    location_data.asn_description = asn_data.get('asn_description')
                    if not location_data.isp:
                        location_data.isp = asn_data.get('asn_description') or asn_data.get('network_name')
            
            # Cache the result
            self.cache[cache_key] = (location_data, time.time())
            
            return location_data
            
        except Exception as e:
            logger.debug(f"Geolocation error for {ip}: {e}")
            return None
    
    async def save_location_data(self, db, location_data: LocationData) -> bool:
        """Save location data to database"""
        try:
            # This would use the database manager to store location data
            # Implementation depends on the specific database backend
            return True
        except Exception as e:
            logger.error(f"Failed to save location data for {location_data.ip}: {e}")
            return False
    
    async def close(self) -> None:
        """Cleanup resources"""
        if self.geo_provider:
            await self.geo_provider.close() 