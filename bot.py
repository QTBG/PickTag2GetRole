import discord
from discord.ext import commands
import os
import json
import asyncio
from dotenv import load_dotenv
import aiofiles
from typing import Dict, List, Optional

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
        self.config_file = 'server_configs.json'
        self.configs: Dict[int, Dict] = {}
        self.update_lock = asyncio.Lock()
        
    async def setup_hook(self):
        """Initialiser le bot"""
        await self.load_configs()
        await self.load_extension('cogs.tag_monitor')
        await self.load_extension('cogs.commands')
        print(f"Bot prêt! Connecté en tant que {self.user}")
        
    async def load_configs(self):
        """Charger les configurations depuis le fichier"""
        try:
            async with aiofiles.open(self.config_file, 'r') as f:
                content = await f.read()
                self.configs = json.loads(content) if content else {}
                # Convertir les clés string en int
                self.configs = {int(k): v for k, v in self.configs.items()}
        except FileNotFoundError:
            self.configs = {}
        except Exception as e:
            print(f"Erreur lors du chargement des configs: {e}")
            self.configs = {}
    
    async def save_configs(self):
        """Sauvegarder les configurations dans le fichier"""
        async with self.update_lock:
            try:
                async with aiofiles.open(self.config_file, 'w') as f:
                    await f.write(json.dumps(self.configs, indent=2))
            except Exception as e:
                print(f"Erreur lors de la sauvegarde des configs: {e}")
    
    def get_guild_config(self, guild_id: int) -> Optional[Dict]:
        """Obtenir la configuration d'un serveur"""
        return self.configs.get(guild_id)
    
    async def set_guild_config(self, guild_id: int, config: Dict):
        """Définir la configuration d'un serveur"""
        self.configs[guild_id] = config
        await self.save_configs()

# Créer et lancer le bot
bot = PickTag2GetRole()

@bot.event
async def on_ready():
    """Événement déclenché quand le bot est prêt"""
    print(f'Bot connecté en tant que {bot.user.name}')
    print(f'ID: {bot.user.id}')
    print(f'Serveurs: {len(bot.guilds)}')
    
    # Synchroniser les commandes slash
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"Erreur lors de la synchronisation des commandes: {e}")

async def main():
    """Fonction principale pour lancer le bot"""
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("ERREUR: Token Discord non trouvé dans le fichier .env")
        return
    
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())