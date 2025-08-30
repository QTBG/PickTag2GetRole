FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances Python d'abord (pour le cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste de l'application
COPY . .

# Créer le dossier data avec permissions ouvertes
RUN mkdir -p /app/data && chmod -R 777 /app/data

# Commande pour lancer le bot
CMD ["python", "-u", "bot.py"]