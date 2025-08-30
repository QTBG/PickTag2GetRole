#!/bin/sh
# Script d'entrée pour le conteneur Docker

# Vérifier si le répertoire data existe et est accessible
if [ -d "/app/data" ]; then
    echo "Data directory exists at /app/data"
    
    # Tenter de créer un fichier test
    if touch /app/data/.test 2>/dev/null; then
        echo "Data directory is writable"
        rm -f /app/data/.test
        
        # S'assurer que le fichier de base de données existe
        if [ ! -f "/app/data/bot_data.db" ]; then
            echo "Creating database file..."
            touch /app/data/bot_data.db
        fi
    else
        echo "ERROR: Data directory is not writable!"
        echo "Please ensure the data directory has proper permissions on the host:"
        echo "  sudo mkdir -p $(pwd)/data"
        echo "  sudo chown -R 1000:1000 $(pwd)/data"
        echo "  sudo chmod -R 755 $(pwd)/data"
        exit 1
    fi
else
    echo "WARNING: Data directory does not exist at /app/data"
    echo "The database will be created in a temporary location"
fi

# Lancer le bot
exec python -u bot.py