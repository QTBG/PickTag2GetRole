FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Créer un utilisateur non-root dès le début
RUN useradd -m -u 1000 botuser

# Copier les fichiers de requirements avec le bon propriétaire
COPY --chown=botuser:botuser requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste de l'application avec le bon propriétaire
COPY --chown=botuser:botuser . .

# Créer le dossier data et définir les permissions
RUN mkdir -p /app/data && chown -R botuser:botuser /app/data

# Changer vers l'utilisateur non-root
USER botuser

# Commande pour lancer le bot
CMD ["python", "-u", "bot.py"]