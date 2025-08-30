#!/bin/bash
# Script pour préparer l'environnement sur l'hôte avant de lancer Docker

echo "Setting up host environment for PickTag2GetRole bot..."

# Créer le répertoire data avec les bonnes permissions
# L'UID 1000 correspond à l'utilisateur botuser dans le conteneur
echo "Creating data directory..."
mkdir -p ./data

# Définir les permissions pour que l'utilisateur du conteneur (UID 1000) puisse écrire
echo "Setting permissions..."
sudo chown -R 1000:1000 ./data
sudo chmod -R 755 ./data

# Créer le fichier de base de données vide
echo "Creating empty database file..."
touch ./data/bot_data.db
sudo chown 1000:1000 ./data/bot_data.db
sudo chmod 664 ./data/bot_data.db

echo "Setup complete! You can now run: docker-compose up -d"
echo ""
echo "If you still have permission issues, try:"
echo "  sudo chmod -R 777 ./data"
echo "  (Note: This is less secure but will ensure the bot can write to the database)"