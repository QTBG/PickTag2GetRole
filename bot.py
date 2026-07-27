import discord
from discord.ext import commands, tasks
import math
import os
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone

import asyncio
from dotenv import load_dotenv

from typing import Dict, Optional
from crypto import EncryptionKeyError
from database import DatabaseManager
from i18n import t, CommandTranslator

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
        self.synced = False
        self.start_time = time.monotonic()

        # Sauvegardes quotidiennes de la base
        self.backup_enabled = os.getenv('BACKUP_ENABLED', 'true').strip().lower() in ('1', 'true', 'yes', 'on')
        try:
            self.backup_keep = max(1, int(os.getenv('BACKUP_KEEP', '7')))
        except ValueError:
            self.backup_keep = 7
        self.last_backup_at: Optional[datetime] = None
        self.db_integrity: Optional[str] = None

        # Fichier de heartbeat lu par le HEALTHCHECK Docker (Dokploy, docker ps...)
        self.heartbeat_file = os.getenv('HEARTBEAT_FILE', '/tmp/picktag_heartbeat')
        
    async def setup_hook(self):
        """Initialiser le bot"""
        # Localisation native des commandes slash (appliquée à la synchronisation)
        await self.tree.set_translator(CommandTranslator())

        await self.db.initialize()

        await self.load_configs_to_cache()
        await self.load_extension('cogs.tag_monitor')
        await self.load_extension('cogs.commands')

        # Gestionnaire d'erreur simple pour les commandes en DM
        self.tree.on_error = self.on_app_command_error

        if self.backup_enabled:
            self.daily_backup.start()
        else:
            logger.info("Database backups disabled (BACKUP_ENABLED=false)")

        self.heartbeat.start()

        logger.info(f"Bot ready! Connected as {self.user}")

    @tasks.loop(minutes=1)
    async def heartbeat(self):
        """Toucher le fichier de heartbeat tant que la gateway répond.

        Si le process se fige ou perd la connexion Discord, le fichier cesse
        d'être mis à jour et le HEALTHCHECK du conteneur passe en "unhealthy".
        """
        if self.is_closed() or not math.isfinite(self.latency):
            return
        try:
            with open(self.heartbeat_file, 'w') as f:
                f.write(str(int(time.time())))
        except OSError as e:
            logger.warning(f"Could not write heartbeat file: {e}")

    @heartbeat.before_loop
    async def before_heartbeat(self):
        await self.wait_until_ready()

    @tasks.loop(hours=24)
    async def daily_backup(self):
        """Sauvegarde quotidienne de la base, précédée d'un contrôle d'intégrité"""
        try:
            result = await self.db.integrity_check()
            self.db_integrity = result
            if result != 'ok':
                # Ne surtout pas écraser ni purger les sauvegardes saines existantes
                logger.error(f"DATABASE INTEGRITY CHECK FAILED ({result}) — "
                             f"skipping backup and rotation; restore from data/backups/")
                return
            path = await self.db.backup(keep=self.backup_keep)
            self.last_backup_at = datetime.now(timezone.utc)
            logger.info(f"Database backup written: {path} ({os.path.getsize(path) / 1024:.0f} KB)")
        except Exception as e:
            logger.error(f"Database backup failed: {e}")

    @daily_backup.before_loop
    async def before_daily_backup(self):
        await self.wait_until_ready()
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Minimal error handler for slash commands"""
        locale = interaction.locale
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            message = t(locale, 'err.cooldown', seconds=int(error.retry_after) + 1)
        elif isinstance(error, (discord.app_commands.TransformerError, discord.app_commands.NoPrivateMessage)):
            message = t(locale, 'err.guild_only')
        elif isinstance(error, discord.app_commands.CheckFailure):
            message = t(locale, 'err.not_allowed')
        else:
            logger.error(f"Command error: {error}")
            message = t(locale, 'err.generic')

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass
        
    async def load_configs_to_cache(self):
        """Load all enabled configurations to cache for performance"""
        try:
            self.config_cache = await self.db.get_all_enabled_configs()
        except EncryptionKeyError:
            # Surtout ne pas avaler : démarrer avec un cache vide désactiverait
            # silencieusement tous les serveurs (healthcheck au vert), et toute
            # reconfiguration pendant l'incident écrirait sous la mauvaise clé.
            # L'exception remonte via setup_hook et le processus sort en erreur.
            raise
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

# Créer et lancer le bot. La construction valide ENCRYPTION_KEY (FieldCipher) :
# une clé malformée lève ici, avant le try de fin de fichier — donner le même
# message actionnable plutôt qu'une traceback brute.
try:
    bot = PickTag2GetRole()
except EncryptionKeyError as e:
    logger.critical("Encryption key problem: %s", e)
    raise SystemExit(1)

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

    # Synchroniser les commandes slash (une seule fois : on_ready se re-déclenche
    # à chaque reconnexion et la synchro est fortement rate-limitée par Discord)
    if not bot.synced:
        try:
            synced = await bot.tree.sync()
            bot.synced = True
            logger.info(f"{len(synced)} commands synced")
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")

async def main():
    """Fonction principale pour lancer le bot"""
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("Discord token not found in .env file")
        return

    if bot.db.cipher.enabled:
        logger.info("Encryption at rest: enabled")
    else:
        logger.warning("Encryption at rest: disabled (no ENCRYPTION_KEY set)")

    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except EncryptionKeyError as e:
        # Mieux vaut refuser de démarrer que tourner avec des données illisibles
        # et écraser des configurations valides.
        logger.critical("Encryption key problem: %s", e)
        raise SystemExit(1)