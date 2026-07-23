import json
import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
import aiosqlite
from contextlib import asynccontextmanager

# Durée de conservation des statistiques agrégées (compteurs journaliers, sans ID utilisateur)
STATS_RETENTION_DAYS = 365

class DatabaseManager:
    def __init__(self, db_path: str = 'data/bot_data.db'):
        # Créer le répertoire data s'il n'existe pas
        data_dir = os.path.dirname(db_path)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
        
        self.db_path = db_path
        self.init_lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize the database with required tables"""
        async with self.init_lock:
            async with aiosqlite.connect(self.db_path) as db:
                # WAL : écritures moins coûteuses et lectures non bloquantes
                # (propriété persistante du fichier, définie une seule fois)
                await db.execute('PRAGMA journal_mode=WAL')
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
                # Statistiques agrégées : un compteur par serveur et par jour, aucun ID utilisateur
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS tag_stats (
                        guild_id INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        tagged_count INTEGER NOT NULL,
                        member_count INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (guild_id, date)
                    )
                ''')
                await db.commit()
    
    @asynccontextmanager
    async def get_db(self):
        """Get a database connection"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA busy_timeout=5000')
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
        """Delete configuration and statistics for a specific guild"""
        async with self.get_db() as db:
            await db.execute('DELETE FROM guild_configs WHERE guild_id = ?', (guild_id,))
            await db.execute('DELETE FROM tag_stats WHERE guild_id = ?', (guild_id,))
            await db.commit()

    async def record_tag_stat(self, guild_id: int, tagged_count: int, member_count: int):
        """Record today's aggregated counters for a guild (one row per guild per day)"""
        async with self.get_db() as db:
            await db.execute('''
                INSERT OR REPLACE INTO tag_stats (guild_id, date, tagged_count, member_count)
                VALUES (?, date('now'), ?, ?)
            ''', (guild_id, tagged_count, member_count))
            # Purge au fil de l'eau pour borner l'espace disque
            await db.execute(
                "DELETE FROM tag_stats WHERE guild_id = ? AND date < date('now', ?)",
                (guild_id, f'-{STATS_RETENTION_DAYS} days')
            )
            await db.commit()

    async def get_tag_stats(self, guild_id: int, days: int = 30) -> List[Dict]:
        """Get daily aggregated counters for a guild, oldest first"""
        async with self.get_db() as db:
            async with db.execute(
                "SELECT date, tagged_count, member_count FROM tag_stats "
                "WHERE guild_id = ? AND date >= date('now', ?) ORDER BY date ASC",
                (guild_id, f'-{days} days')
            ) as cursor:
                return [
                    {'date': row[0], 'tagged': row[1], 'members': row[2]}
                    async for row in cursor
                ]

    async def integrity_check(self) -> str:
        """Run PRAGMA quick_check on the database ('ok' means healthy)"""
        async with self.get_db() as db:
            async with db.execute('PRAGMA quick_check') as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 'unknown'

    async def backup(self, keep: int = 7) -> str:
        """Write a consistent snapshot of the database, one file per UTC day.

        Utilise l'API de sauvegarde en ligne de SQLite : le snapshot est cohérent
        même si le bot écrit en même temps (un simple `cp` ne l'est pas, surtout
        en mode WAL). Écriture atomique via un fichier temporaire, puis rotation :
        seuls les `keep` fichiers les plus récents sont conservés.
        """
        backup_dir = os.path.join(os.path.dirname(self.db_path) or '.', 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
        dest = os.path.join(backup_dir, f'bot_data-{date_str}.db')
        tmp = dest + '.tmp'

        try:
            async with aiosqlite.connect(self.db_path) as src:
                async with aiosqlite.connect(tmp) as dst:
                    await src.backup(dst)
            os.replace(tmp, dest)
        finally:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass

        if keep > 0:
            existing = sorted(
                name for name in os.listdir(backup_dir)
                if name.startswith('bot_data-') and name.endswith('.db')
            )
            for old_name in existing[:-keep]:
                try:
                    os.remove(os.path.join(backup_dir, old_name))
                except OSError:
                    pass

        return dest
    
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