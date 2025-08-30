#!/bin/bash
# Script de déploiement pour PickTag2GetRole

echo "📦 Mise à jour du code..."
git pull

# Préparer l'environnement si nécessaire
if [ ! -d "./data" ]; then
    echo "🔧 Préparation de l'environnement..."
    ./setup-host.sh
else
    # Vérifier quand même les permissions
    if [ ! -w "./data" ]; then
        echo "⚠️  Réparation des permissions du répertoire data..."
        sudo chown -R 1000:1000 ./data
        sudo chmod -R 755 ./data
    fi
fi

echo "🛑 Arrêt du conteneur..."
docker-compose down

echo "🔨 Construction de l'image (sans cache)..."
docker-compose build --no-cache

echo "🚀 Démarrage du bot..."
docker-compose up -d

echo "📋 Affichage des logs..."
docker-compose logs -f