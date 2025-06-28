"""
Enhanced database management with support for multiple backends
"""

import asyncio
import sqlite3
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
from pathlib import Path
import aiosqlite

try:
    import asyncpg
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

from .exceptions import DatabaseError
from .config_types import DatabaseConfig

logger = logging.getLogger(__name__)

class DatabaseBackend(ABC):
    """Abstract base class for database backends"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize database connection and schema"""
        pass
    
    @abstractmethod
    async def store_server(self, scan_result) -> bool:
        """Store server scan result"""
        pass
    
    @abstractmethod
    async def get_server(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """Get server information"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close database connection"""
        pass

class SQLiteBackend(DatabaseBackend):
    """SQLite database backend"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.db_path = config.path
        self.connection = None
    
    async def initialize(self) -> None:
        """Initialize SQLite database"""
        try:
            # Create directory if needed
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Create database schema
            await self._create_schema()
            logger.info(f"SQLite database initialized: {self.db_path}")
        except Exception as e:
            raise DatabaseError(f"Failed to initialize SQLite database: {e}")
    
    async def _create_schema(self) -> None:
        """Create database schema"""
        schema_sql = """
        -- Main servers table
        CREATE TABLE IF NOT EXISTS servers (
            ip TEXT NOT NULL,
            port INTEGER NOT NULL DEFAULT 25565,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_online TIMESTAMP,
            total_scans INTEGER DEFAULT 1,
            successful_scans INTEGER DEFAULT 0,
            availability_percentage REAL DEFAULT 0.0,
            PRIMARY KEY (ip, port)
        );

        -- Server status snapshots
        CREATE TABLE IF NOT EXISTS server_status (
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            online_mode TEXT CHECK(online_mode IN ('online', 'offline', 'unknown')),
            latency_ms INTEGER,
            minecraft_version TEXT,
            protocol_version INTEGER,
            server_software TEXT,
            motd_raw TEXT,
            motd_clean TEXT,
            favicon_hash TEXT,
            max_players INTEGER,
            online_players INTEGER,
            enforces_secure_chat BOOLEAN,
            prevents_chat_reports BOOLEAN,
            PRIMARY KEY (ip, port, scan_time)
        );

        -- Players table
        CREATE TABLE IF NOT EXISTS players (
            uuid TEXT PRIMARY KEY,
            last_known_name TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_servers_seen INTEGER DEFAULT 1
        );

        -- Player sessions
        CREATE TABLE IF NOT EXISTS player_sessions (
            uuid TEXT NOT NULL,
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            seen_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            player_name TEXT,
            PRIMARY KEY (uuid, ip, port, seen_time)
        );

        -- Mods table
        CREATE TABLE IF NOT EXISTS mods (
            mod_id TEXT PRIMARY KEY,
            mod_name TEXT,
            mod_type TEXT CHECK(mod_type IN ('forge', 'fabric', 'quilt', 'bukkit', 'spigot', 'paper', 'plugin')),
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Server mods association
        CREATE TABLE IF NOT EXISTS server_mods (
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            mod_id TEXT NOT NULL,
            mod_version TEXT,
            detected_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (ip, port, mod_id)
        );

        -- Favicons
        CREATE TABLE IF NOT EXISTS favicons (
            favicon_hash TEXT PRIMARY KEY,
            favicon_data TEXT NOT NULL,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usage_count INTEGER DEFAULT 1
        );

        -- Server locations
        CREATE TABLE IF NOT EXISTS server_locations (
            ip TEXT PRIMARY KEY,
            country_code TEXT,
            country_name TEXT,
            region TEXT,
            city TEXT,
            latitude REAL,
            longitude REAL,
            isp TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- IP Blacklist
        CREATE TABLE IF NOT EXISTS ip_blacklist (
            ip TEXT PRIMARY KEY,
            reason TEXT,
            added_by TEXT DEFAULT 'system',
            added_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_servers_last_online ON servers(last_online);
        CREATE INDEX IF NOT EXISTS idx_server_status_version ON server_status(minecraft_version);
        CREATE INDEX IF NOT EXISTS idx_server_status_software ON server_status(server_software);
        CREATE INDEX IF NOT EXISTS idx_server_status_online_mode ON server_status(online_mode);
        CREATE INDEX IF NOT EXISTS idx_players_last_seen ON players(last_seen);
        CREATE INDEX IF NOT EXISTS idx_blacklist_ip ON ip_blacklist(ip);
        """
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema_sql)
            await db.commit()
    
    async def store_server(self, scan_result) -> bool:
        """Store server scan result in SQLite"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Store main server record
                await db.execute("""
                    INSERT OR REPLACE INTO servers 
                    (ip, port, last_seen, total_scans, successful_scans, availability_percentage)
                    VALUES (?, ?, CURRENT_TIMESTAMP, 
                           COALESCE((SELECT total_scans FROM servers WHERE ip = ? AND port = ?), 0) + 1,
                           COALESCE((SELECT successful_scans FROM servers WHERE ip = ? AND port = ?), 0) + 1,
                           CASE 
                               WHEN COALESCE((SELECT total_scans FROM servers WHERE ip = ? AND port = ?), 0) + 1 > 0
                               THEN (COALESCE((SELECT successful_scans FROM servers WHERE ip = ? AND port = ?), 0) + 1.0) / 
                                    (COALESCE((SELECT total_scans FROM servers WHERE ip = ? AND port = ?), 0) + 1) * 100
                               ELSE 0
                           END)
                """, (scan_result.ip, scan_result.port, scan_result.ip, scan_result.port,
                     scan_result.ip, scan_result.port, scan_result.ip, scan_result.port,
                     scan_result.ip, scan_result.port, scan_result.ip, scan_result.port))
                
                # Store server status if data available
                if scan_result.server_data:
                    data = scan_result.server_data
                    await db.execute("""
                        INSERT INTO server_status 
                        (ip, port, online_mode, latency_ms, minecraft_version, protocol_version,
                         server_software, motd_raw, motd_clean, max_players, online_players,
                         enforces_secure_chat, prevents_chat_reports)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        scan_result.ip, scan_result.port, data.get('online_mode', 'unknown'),
                        int(scan_result.latency) if scan_result.latency else None,
                        data.get('version_name'), data.get('protocol_version'),
                        data.get('server_type'), data.get('motd_raw'), data.get('motd_formatted'),
                        data.get('max_players'), data.get('online_players'),
                        data.get('enforces_secure_chat'), data.get('prevents_chat_reports')
                    ))
                
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to store server {scan_result.ip}:{scan_result.port}: {e}")
            return False
    
    async def get_server(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """Get server information from SQLite"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT s.*, ss.minecraft_version, ss.server_software, ss.motd_clean
                    FROM servers s
                    LEFT JOIN (
                        SELECT ip, port, minecraft_version, server_software, motd_clean,
                               ROW_NUMBER() OVER (PARTITION BY ip, port ORDER BY scan_time DESC) as rn
                        FROM server_status
                    ) ss ON s.ip = ss.ip AND s.port = ss.port AND ss.rn = 1
                    WHERE s.ip = ? AND s.port = ?
                """, (ip, port)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        columns = [description[0] for description in cursor.description]
                        return dict(zip(columns, row))
            return None
        except Exception as e:
            logger.error(f"Failed to get server {ip}:{port}: {e}")
            return None
    
    async def close(self) -> None:
        """Close SQLite connection"""
        # SQLite connections are closed automatically with context managers
        pass

class PostgreSQLBackend(DatabaseBackend):
    """PostgreSQL database backend"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool = None
    
    async def initialize(self) -> None:
        """Initialize PostgreSQL database"""
        if not POSTGRESQL_AVAILABLE:
            raise DatabaseError("asyncpg is required for PostgreSQL support")
        
        try:
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                min_size=1,
                max_size=self.config.pool_size
            )
            
            # Create schema
            await self._create_schema()
            logger.info(f"PostgreSQL database initialized: {self.config.host}:{self.config.port}")
        except Exception as e:
            raise DatabaseError(f"Failed to initialize PostgreSQL database: {e}")
    
    async def _create_schema(self) -> None:
        """Create PostgreSQL schema"""
        schema_sql = """
        -- Create server software enum
        DO $$ BEGIN
            CREATE TYPE server_software AS ENUM (
                'vanilla', 'paper', 'spigot', 'bukkit', 'purpur', 'folia',
                'pufferfish', 'forge', 'neoforge', 'fabric', 'quilt',
                'velocity', 'bungeecord', 'waterfall', 'unknown'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        
        -- Main servers table
        CREATE TABLE IF NOT EXISTS servers (
            ip INET NOT NULL,
            port INTEGER NOT NULL DEFAULT 25565,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_online TIMESTAMP,
            total_scans INTEGER DEFAULT 1,
            successful_scans INTEGER DEFAULT 0,
            availability_percentage REAL DEFAULT 0.0,
            PRIMARY KEY (ip, port)
        );
        
        -- Server status snapshots
        CREATE TABLE IF NOT EXISTS server_status (
            ip INET NOT NULL,
            port INTEGER NOT NULL,
            scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            online_mode TEXT CHECK(online_mode IN ('online', 'offline', 'unknown')),
            latency_ms INTEGER,
            minecraft_version TEXT,
            protocol_version INTEGER,
            server_software server_software,
            motd_raw TEXT,
            motd_clean TEXT,
            favicon_hash TEXT,
            max_players INTEGER,
            online_players INTEGER,
            enforces_secure_chat BOOLEAN,
            prevents_chat_reports BOOLEAN,
            PRIMARY KEY (ip, port, scan_time)
        );
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_servers_last_online ON servers(last_online);
        CREATE INDEX IF NOT EXISTS idx_server_status_version ON server_status(minecraft_version);
        CREATE INDEX IF NOT EXISTS idx_server_status_software ON server_status(server_software);
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(schema_sql)
    
    async def store_server(self, scan_result) -> bool:
        """Store server scan result in PostgreSQL"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO servers (ip, port, last_seen, total_scans, successful_scans)
                    VALUES ($1, $2, CURRENT_TIMESTAMP, 
                           COALESCE((SELECT total_scans FROM servers WHERE ip = $1 AND port = $2), 0) + 1,
                           COALESCE((SELECT successful_scans FROM servers WHERE ip = $1 AND port = $2), 0) + 1)
                    ON CONFLICT (ip, port) DO UPDATE SET
                        last_seen = CURRENT_TIMESTAMP,
                        total_scans = servers.total_scans + 1,
                        successful_scans = servers.successful_scans + 1,
                        availability_percentage = (servers.successful_scans + 1.0) / (servers.total_scans + 1) * 100
                """, scan_result.ip, scan_result.port)
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to store server {scan_result.ip}:{scan_result.port}: {e}")
            return False
    
    async def get_server(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """Get server information from PostgreSQL"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM servers WHERE ip = $1 AND port = $2
                """, ip, port)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get server {ip}:{port}: {e}")
            return None
    
    async def close(self) -> None:
        """Close PostgreSQL connection pool"""
        if self.pool:
            await self.pool.close()

class DatabaseManager:
    """Main database manager that handles different backends"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.backend = self._create_backend()
    
    def _create_backend(self) -> DatabaseBackend:
        """Create appropriate database backend"""
        if self.config.type.lower() == "sqlite":
            return SQLiteBackend(self.config)
        elif self.config.type.lower() == "postgresql":
            return PostgreSQLBackend(self.config)
        else:
            raise DatabaseError(f"Unsupported database type: {self.config.type}")
    
    async def initialize(self) -> None:
        """Initialize database"""
        await self.backend.initialize()
    
    async def store_server(self, scan_result) -> bool:
        """Store server scan result"""
        return await self.backend.store_server(scan_result)
    
    async def get_server(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """Get server information"""
        return await self.backend.get_server(ip, port)
    
    async def close(self) -> None:
        """Close database connection"""
        await self.backend.close() 