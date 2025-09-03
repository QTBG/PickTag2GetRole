import discord
from discord.ext import commands
import os
import logging

import asyncio
from dotenv import load_dotenv

from typing import Dict, List, Optional
from database import DatabaseManager

# Charger les variables d'environnement EN PREMIER
load_dotenv()

# Configuration du logging APRÈS le chargement des variables d'environnement
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('PickTag2GetRole')
logger.info(f"Logging level set to: {log_level}")
logger.info(f"Discord.py version: {discord.__version__}")

# Configuration optimisée pour un VPS léger
intents = discord.Intents.all()
intents.guilds = True
intents.members = True
intents.presences = True  # Nécessaire pour accéder à primary_guild
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

        await self.load_configs_to_cache()
        await self.load_extension('cogs.tag_monitor')
        await self.load_extension('cogs.commands')
        
        # Gestionnaire d'erreur simple pour les commandes en DM
        self.tree.on_error = self.on_app_command_error
        
        logger.info(f"Bot ready! Connected as {self.user}")
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Gestionnaire d'erreur minimal pour les commandes slash"""
        if isinstance(error, discord.app_commands.TransformerError):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Cette commande ne peut être utilisée qu'dans un serveur, pas en DM.",
                    ephemeral=True
                )
        elif isinstance(error, discord.app_commands.CommandInvokeError):
            if "'User' object has no attribute 'guild_permissions'" in str(error):
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Cette commande ne peut être utilisée qu'dans un serveur, pas en DM.",
                        ephemeral=True
                    )
            else:
                logger.error(f"Command error: {error}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Une erreur s'est produite lors de l'exécution de la commande.",
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