#!/bin/bash
# Script de déploiement pour PickTag2GetRole

echo "📦 Mise à jour du code..."
git pull

echo "🛑 Arrêt du conteneur..."
docker-compose down

echo "🔨 Construction de l'image (sans cache)..."
docker-compose build --no-cache

echo "🚀 Démarrage du bot..."
docker-compose up -d

echo "📋 Affichage des logs..."
docker-compose logs -f