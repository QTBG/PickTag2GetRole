#!/bin/bash
# Script d'initialisation pour créer le répertoire data avec les bonnes permissions

# Créer le répertoire data s'il n'existe pas
mkdir -p /app/data

# S'assurer que les permissions sont correctes
chmod 755 /app/data

# Créer le fichier de base de données vide s'il n'existe pas
touch /app/data/bot_data.db
chmod 664 /app/data/bot_data.db

# S'assurer que l'utilisateur botuser possède tout
chown -R botuser:botuser /app/data

echo "Database directory initialized successfully"