FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Copier les fichiers de requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste de l'application
COPY . .

# Créer le dossier data avec les bonnes permissions
RUN mkdir -p /app/data

# Créer un utilisateur non-root pour la sécurité
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Commande pour lancer le bot
CMD ["python", "-u", "bot.py"]