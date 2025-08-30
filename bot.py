import discord
from discord.ext import commands
import os
import json
import asyncio
from dotenv import load_dotenv
import aiofiles
from typing import Dict, List, Optional
from database import DatabaseManager

# Charger les variables d'environnement
load_dotenv()

# Configuration optimisée pour un VPS léger
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.guild_messages = False  # Désactiver les messages pour économiser des ressources
intents.message_content = False

class PickTag2GetRole(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',  # Prefix non utilisé mais requis
            intents=intents,
            help_command=None,
            chunk_guilds_at_startup=False  # Ne pas charger tous les membres au démarrage
        )
        self.db = DatabaseManager()
        self.config_cache: Dict[int, Dict] = {}
        self.cache_lock = asyncio.Lock()
        
    async def setup_hook(self):
        """Initialiser le bot"""
        await self.db.initialize()
        await self.migrate_from_json()  # Migrate old data if exists
        await self.load_configs_to_cache()
        await self.load_extension('cogs.tag_monitor')
        await self.load_extension('cogs.commands')
        print(f"Bot ready! Connected as {self.user}")
        
    async def load_configs_to_cache(self):
        """Load all enabled configurations to cache for performance"""
        try:
            self.config_cache = await self.db.get_all_enabled_configs()
        except Exception as e:
            print(f"Error loading configs to cache: {e}")
            self.config_cache = {}
    
    async def migrate_from_json(self):
        """Migrate from old JSON file to database (one-time migration)"""
        if os.path.exists('server_configs.json'):
            try:
                async with aiofiles.open('server_configs.json', 'r') as f:
                    content = await f.read()
                    old_configs = json.loads(content) if content else {}
                    
                # Migrate each server config
                for guild_id_str, config in old_configs.items():
                    guild_id = int(guild_id_str)
                    await self.db.set_guild_config(guild_id, config)
                    print(f"Migrated config for guild {guild_id}")
                
                # Rename old file to backup
                os.rename('server_configs.json', 'server_configs.json.backup')
                print("Migration complete! Old file backed up as server_configs.json.backup")
            except Exception as e:
                print(f"Error during migration: {e}")
    
    async def refresh_cache(self, guild_id: int):
        """Refresh cache for a specific guild"""
        async with self.cache_lock:
            config = await self.db.get_guild_config(guild_id)
            if config and config.get('enabled', False):
                self.config_cache[guild_id] = config
            elif guild_id in self.config_cache:
                del self.config_cache[guild_id]
    
    async def get_guild_config(self, guild_id: int) -> Optional[Dict]:
        """Get guild configuration from database"""
        return await self.db.get_guild_config(guild_id)
    
    def get_guild_config_cached(self, guild_id: int) -> Optional[Dict]:
        """Get guild configuration from cache (for performance)"""
        return self.config_cache.get(guild_id)
    
    async def set_guild_config(self, guild_id: int, config: Dict):
        """Set guild configuration in database"""
        await self.db.set_guild_config(guild_id, config)
        await self.refresh_cache(guild_id)

# Créer et lancer le bot
bot = PickTag2GetRole()

@bot.event
async def on_guild_remove(guild: discord.Guild):
    """When bot is removed from a server, delete its data"""
    await bot.db.delete_guild_config(guild.id)
    print(f"Bot removed from {guild.name} ({guild.id}), data deleted")

@bot.event
async def on_ready():
    """Événement déclenché quand le bot est prêt"""
    print(f'Bot connected as {bot.user.name}')
    print(f'ID: {bot.user.id}')
    print(f'Servers: {len(bot.guilds)}')
    
    # Synchroniser les commandes slash
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} commands synced")
    except Exception as e:
        print(f"Error syncing commands: {e}")

async def main():
    """Fonction principale pour lancer le bot"""
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("ERROR: Discord token not found in .env file")
        return
    
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())