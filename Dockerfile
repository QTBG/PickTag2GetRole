FROM python:3.11-slim

# Ne pas exécuter le bot en root dans le conteneur
RUN useradd --create-home --shell /usr/sbin/nologin botuser

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances Python d'abord (pour le cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste de l'application
COPY . .

# Créer le dossier data (base SQLite), propriété de l'utilisateur non-root
RUN mkdir -p /app/data && chown -R botuser:botuser /app

USER botuser

# Commande pour lancer le bot
CMD ["python", "-u", "bot.py"]
