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
#
# interval court (10s) : le premier contrôle n'a lieu qu'après un intervalle,
# et les orchestrateurs (Dokploy, Swarm) attendent l'état "healthy" pour valider
# un déploiement — avec un intervalle long, le déploiement expire avant.
# Le contrôle utilise `find` plutôt qu'un interpréteur Python : ~2 ms au lieu
# de ~40 ms, ce qui compte à cette fréquence sur un petit VPS.
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD find "${HEARTBEAT_FILE:-/tmp/picktag_heartbeat}" -newermt '-300 seconds' 2>/dev/null | grep -q .

# Commande pour lancer le bot
CMD ["python", "-u", "bot.py"]
