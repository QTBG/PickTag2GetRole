import sqlite3
import json
import asyncio
import os
from typing import Dict, Optional
import aiosqlite
from contextlib import asynccontextmanager

class DatabaseManager:
    def __init__(self, db_path: str = 'data/bot_data.db'):
        # Ensure data directory exists with proper permissions
        data_dir = os.path.dirname(db_path)
        if data_dir:
            try:
                os.makedirs(data_dir, exist_ok=True, mode=0o755)
                # Ensure the directory is writable
                if not os.access(data_dir, os.W_OK):
                    print(f"Warning: Directory {data_dir} is not writable")
            except PermissionError as e:
                print(f"Permission error creating directory {data_dir}: {e}")
                # Try to use /tmp as fallback
                self.db_path = '/tmp/bot_data.db'
                print(f"Using fallback database path: {self.db_path}")
            except Exception as e:
                print(f"Error creating directory {data_dir}: {e}")
                self.db_path = '/tmp/bot_data.db'
                print(f"Using fallback database path: {self.db_path}")
        
        if not hasattr(self, 'db_path'):
            self.db_path = db_path
            
        self.init_lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize the database with required tables"""
        async with self.init_lock:
            try:
                # Ensure the database file exists and is writable
                db_dir = os.path.dirname(self.db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True, mode=0o755)
                
                # Touch the file to ensure it exists
                if not os.path.exists(self.db_path):
                    # Create an empty file
                    open(self.db_path, 'a').close()
                    os.chmod(self.db_path, 0o664)
                
                async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS guild_configs (
                        guild_id INTEGER PRIMARY KEY,
                        tag_to_watch TEXT,
                        role_ids TEXT,
                        enabled INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                await db.commit()
                print(f"Database initialized successfully at {self.db_path}")
            except Exception as e:
                print(f"Error initializing database: {e}")
                raise
    
    @asynccontextmanager
    async def get_db(self):
        """Get a database connection"""
        async with aiosqlite.connect(self.db_path) as db:
            yield db
    
    async def get_guild_config(self, guild_id: int) -> Optional[Dict]:
        """Get configuration for a specific guild"""
        async with self.get_db() as db:
            async with db.execute(
                'SELECT tag_to_watch, role_ids, enabled FROM guild_configs WHERE guild_id = ?',
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    return {
                        'tag_to_watch': row[0],
                        'role_ids': json.loads(row[1]) if row[1] else [],
                        'enabled': bool(row[2])
                    }
                return None
    
    async def set_guild_config(self, guild_id: int, config: Dict):
        """Set configuration for a specific guild"""
        async with self.get_db() as db:
            role_ids_json = json.dumps(config.get('role_ids', []))
            
            await db.execute('''
                INSERT OR REPLACE INTO guild_configs 
                (guild_id, tag_to_watch, role_ids, enabled, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                guild_id,
                config.get('tag_to_watch'),
                role_ids_json,
                int(config.get('enabled', True))
            ))
            await db.commit()
    
    async def delete_guild_config(self, guild_id: int):
        """Delete configuration for a specific guild"""
        async with self.get_db() as db:
            await db.execute('DELETE FROM guild_configs WHERE guild_id = ?', (guild_id,))
            await db.commit()
    
    async def get_all_enabled_configs(self) -> Dict[int, Dict]:
        """Get all enabled configurations (for monitoring)"""
        async with self.get_db() as db:
            async with db.execute(
                'SELECT guild_id, tag_to_watch, role_ids FROM guild_configs WHERE enabled = 1'
            ) as cursor:
                configs = {}
                async for row in cursor:
                    configs[row[0]] = {
                        'tag_to_watch': row[1],
                        'role_ids': json.loads(row[2]) if row[2] else [],
                        'enabled': True
                    }
                return configs