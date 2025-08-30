# Résolution du problème de permissions SQLite

## Problème
L'erreur `sqlite3.OperationalError: unable to open database file` se produit car :
1. Le répertoire `data/` n'existe pas sur l'hôte
2. Ou il existe mais avec les mauvaises permissions (appartient à root)
3. L'utilisateur du conteneur (UID 1000) ne peut pas y écrire

## Solution rapide

### Option 1 : Utiliser le script de setup (recommandé)
```bash
# Exécuter avant le premier lancement
chmod +x setup-host.sh
./setup-host.sh

# Puis lancer normalement
docker-compose up -d
```

### Option 2 : Commandes manuelles
```bash
# Créer le répertoire data avec les bonnes permissions
mkdir -p ./data
sudo chown -R 1000:1000 ./data
sudo chmod -R 755 ./data

# Créer le fichier de base de données vide
touch ./data/bot_data.db
sudo chown 1000:1000 ./data/bot_data.db
sudo chmod 664 ./data/bot_data.db

# Relancer
docker-compose down
docker-compose up -d
```

### Option 3 : Permissions ouvertes (moins sécurisé)
```bash
# Si les autres options ne fonctionnent pas
sudo chmod -R 777 ./data
docker-compose restart
```

## Utiliser le nouveau script de déploiement

Le script `deploy.sh` inclut maintenant la vérification et correction automatique des permissions :

```bash
chmod +x deploy.sh
./deploy.sh
```

## Vérification

Pour vérifier que tout fonctionne :
```bash
# Vérifier les permissions
ls -la ./data/

# Vérifier les logs
docker-compose logs -f
```

## Explications techniques

- L'utilisateur `botuser` dans le conteneur a l'UID 1000
- Le répertoire `./data` est monté comme volume dans `/app/data`
- Si les permissions ne correspondent pas, SQLite ne peut pas créer/ouvrir le fichier
- Le nouveau code inclut des mécanismes de fallback et de meilleurs messages d'erreur