import discord
from discord.ext import commands
import os
import logging
from logging.handlers import RotatingFileHandler

import asyncio
from dotenv import load_dotenv

from typing import Dict, Optional
from database import DatabaseManager

# Charger les variables d'environnement EN PREMIER
load_dotenv()

# Configuration du logging APRÈS le chargement des variables d'environnement
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
# LOG_FILE="" désactive le fichier (ex: sous Docker, stdout suffit et Docker gère la rotation)
log_file = os.getenv('LOG_FILE', 'bot.log')

log_handlers: list = [logging.StreamHandler()]
if log_file:
    # Rotation pour ne jamais remplir le disque du VPS : 5 Mo x 3 fichiers max
    log_handlers.append(RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'))

logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger('PickTag2GetRole')
logger.info(f"Logging level set to: {log_level}")
logger.info(f"Discord.py version: {discord.__version__}")

# Uniquement les intents réellement nécessaires (moins d'événements = moins de CPU/bande passante,
# et pas de données reçues au-delà de ce que la privacy policy annonce) :
# - guilds : événements de serveur et cache des rôles
# - members (privilégié) : on_member_join/update, fetch_members pour les scans
# - presences (privilégié) : les changements de tag (primary_guild) arrivent via PRESENCE_UPDATE
intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.presences = True

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

        await self.load_configs_to_cache()
        await self.load_extension('cogs.tag_monitor')
        await self.load_extension('cogs.commands')
        
        # Gestionnaire d'erreur simple pour les commandes en DM
        self.tree.on_error = self.on_app_command_error
        
        logger.info(f"Bot ready! Connected as {self.user}")
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Minimal error handler for slash commands"""
        if isinstance(error, discord.app_commands.TransformerError):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ This command can only be used in a server, not in DMs.",
                    ephemeral=True
                )
        elif isinstance(error, discord.app_commands.CommandInvokeError):
            if "'User' object has no attribute 'guild_permissions'" in str(error):
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ This command can only be used in a server, not in DMs.",
                        ephemeral=True
                    )
            else:
                logger.error(f"Command error: {error}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ An error occurred while executing the command.",
                        ephemeral=True
                    )
        
    async def load_configs_to_cache(self):
        """Load all enabled configurations to cache for performance"""
        try:
            self.config_cache = await self.db.get_all_enabled_configs()
        except Exception as e:
            logger.error(f"Error loading configs to cache: {e}")
            self.config_cache = {}
    

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
async def on_guild_join(guild: discord.Guild):
    """When bot joins a new server"""
    logger.info(f"Bot joined server {guild.id} | Total servers: {len(bot.guilds)}")

@bot.event
async def on_guild_remove(guild: discord.Guild):
    """When bot is removed from a server, delete its data"""
    await bot.db.delete_guild_config(guild.id)
    async with bot.cache_lock:
        bot.config_cache.pop(guild.id, None)
    logger.info(f"Bot removed from server {guild.id}, data deleted | Total servers: {len(bot.guilds)}")

@bot.event
async def on_ready():
    """Événement déclenché quand le bot est prêt"""
    logger.info(f'Bot connected as {bot.user.name}')
    logger.info(f'ID: {bot.user.id}')
    logger.info(f'Servers: {len(bot.guilds)}')
    
    # Synchroniser les commandes slash
    try:
        synced = await bot.tree.sync()
        logger.info(f"{len(synced)} commands synced")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")

async def main():
    """Fonction principale pour lancer le bot"""
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("Discord token not found in .env file")
        return
    
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())