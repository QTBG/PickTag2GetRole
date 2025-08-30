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

# Rendre le script d'entrée exécutable
RUN chmod +x /app/docker-entrypoint.sh

# Créer le dossier data dans le conteneur (sera écrasé par le volume monté)
# mais au moins il existera si aucun volume n'est monté
RUN mkdir -p /app/data && chown -R botuser:botuser /app/data

# Changer vers l'utilisateur non-root
USER botuser

# Point d'entrée
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Commande par défaut (peut être surchargée)
CMD []