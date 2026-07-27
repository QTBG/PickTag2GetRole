FROM python:3.11-slim

# Ne pas exécuter le bot en root dans le conteneur.
# UID fixe (1000) pour que les permissions du volume de données soient prévisibles.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin botuser

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances Python d'abord (pour le cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste de l'application
COPY . .

# Créer le dossier data (base SQLite), propriété de l'utilisateur non-root.
# Un volume Docker nommé monté ici hérite de ce propriétaire à sa création.
RUN mkdir -p /app/data && chown -R botuser:botuser /app

USER botuser

# Le bot met à jour un fichier de heartbeat tant que la gateway Discord répond.
# Si le process se fige ou perd la connexion, le conteneur passe "unhealthy".
HEALTHCHECK --interval=60s --timeout=10s --start-period=180s --retries=3 \
    CMD python -c "import os,sys,time; p=os.getenv('HEARTBEAT_FILE','/tmp/picktag_heartbeat'); sys.exit(0 if os.path.exists(p) and time.time()-os.path.getmtime(p) < 300 else 1)"

# Commande pour lancer le bot
CMD ["python", "-u", "bot.py"]
