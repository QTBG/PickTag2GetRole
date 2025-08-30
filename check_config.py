#!/usr/bin/env python3
"""
Script de vérification de la configuration du bot Discord
"""
import os
import sys
from dotenv import load_dotenv

# Charger le fichier .env
load_dotenv()

print("🔍 Vérification de la configuration du bot Discord")
print("=" * 50)

# Vérifier le token
token = os.getenv('DISCORD_TOKEN')
if not token:
    print("❌ ERREUR : Aucun token trouvé dans le fichier .env")
    print("   Assurez-vous d'avoir créé un fichier .env avec DISCORD_TOKEN=votre_token")
    sys.exit(1)
elif len(token) < 50:
    print("⚠️  ATTENTION : Le token semble trop court")
    print("   Un token Discord fait généralement 70+ caractères")
elif not token.count('.') == 2:
    print("⚠️  ATTENTION : Le format du token semble incorrect")
    print("   Un token Discord a le format : XXX.YYY.ZZZ")
else:
    print("✅ Token trouvé et semble valide")
    print(f"   Longueur : {len(token)} caractères")
    print(f"   Format : {token[:6]}...{token[-6:]}")

print("\n📋 Checklist pour le Discord Developer Portal :")
print("=" * 50)
print("Dans l'onglet 'Bot' :")
print("  ✓ Bot créé et token copié")
print("  ✓ SERVER MEMBERS INTENT activé")
print("  ✓ PUBLIC BOT décoché (si bot privé)")
print("\nDans l'onglet 'OAuth2 > URL Generator' :")
print("  ✓ Scopes : bot + applications.commands")
print("  ✓ Permissions : Manage Roles + View Channels")
print("\n🔗 URL d'invitation du bot :")
print("=" * 50)
print("Remplacez YOUR_CLIENT_ID par l'ID de votre application :")
print("https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=268436480&scope=bot%20applications.commands")
print("\nPermissions incluses :")
print("  - Manage Roles (268435456)")
print("  - View Channels (1024)")
print("  Total : 268436480")

print("\n📝 Notes importantes :")
print("=" * 50)
print("- Le bot doit avoir un rôle plus élevé que les rôles qu'il gère")
print("- Invitez le bot AVANT de lancer le script")
print("- Le fichier server_configs.json sera créé automatiquement")

print("\n✅ Si tout est configuré, lancez le bot avec :")
print("   docker-compose up -d")
print("   ou")
print("   python bot.py")