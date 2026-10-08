# Cém'ITX

Application indépendante Python / JavaScript inspirée de Cémantix. Les températures reposent sur de vrais vecteurs sémantiques, sans appel à l’API du jeu original.

## Démarrage

L’environnement et les données ont été préparés dans ce dossier. Dans PowerShell :

```powershell
.\.venv\Scripts\python.exe app.py
```

Ouvrir http://127.0.0.1:5000. `PORT` permet de changer le port.

## Installation sur un autre ordinateur (Python 3.10+)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe prepare_data.py
.\.venv\Scripts\python.exe app.py
```

Téléchargement initial : environ 577 Mo. Prévoir 2 Go de disque libre pour le modèle et sa préparation, et environ 1 Go de RAM. Le modèle original reste conservé. Les démarrages suivants utilisent le cache normalisé sans téléchargement.

Si vous avez déjà le fichier officiel : `python prepare_data.py --source C:\chemin\frWac_postag_no_phrase_700_skip_cut50.bin`. Le MD5 publié par l’auteur est vérifié.

## Déploiement du jeu sur Cloudflare Workers

Pour un projet Cloudflare dont la commande de déploiement est `npx wrangler deploy`, utiliser la configuration `wrangler.jsonc` à la racine du dépôt :

- Commande de build : laisser vide (aucune compilation préalable).
- Commande de déploiement : `npx wrangler deploy`.
- Répertoire racine : racine du dépôt.
- Le nom `c-mitx` dans `wrangler.jsonc` doit correspondre au nom du Worker configuré dans Cloudflare.

`main` désigne `static/_worker.js` comme code du serveur. L’interface est publiée via le binding `ASSETS`. `static/.assetsignore` exclut `_worker.js` et `_routes.json` des fichiers publics, ce qui corrige l’erreur **Uploading a Pages _worker.js file as an asset**. Les routes `/api/*` exécutent le Worker avant la recherche d’un fichier statique. `keep_vars` conserve les variables configurées dans le tableau de bord.

Ajouter `GAME_API_ORIGIN` dans **Settings → Variables and Secrets**, avec l’adresse HTTPS publique du serveur Python (par exemple `https://jeu-api.votre-domaine.fr`), puis redéployer. Un préfixe de chemin est accepté, par exemple `https://vps-a183fa1c.vps.ovh.net/cem-itx` ; le relais lui ajoute `/api/game` ou `/api/guess`. Le build peut réussir sans cette variable, mais le formulaire nécessite ce serveur pour calculer les températures et enregistrer les essais.

Vérification locale sans publication : `npx wrangler deploy --dry-run --outdir artifacts/worker-build`. Prévisualisation : `npx wrangler dev`.

Documentation : [configuration des assets Workers](https://developers.cloudflare.com/workers/static-assets/binding/).

### Serveur permanent sur le VPS

Le serveur Cém’ITX est déployé dans `/opt/cem-itx` sur le VPS Ubuntu `51.195.222.75`, avec Docker Compose et Waitress. Le site utilise `GAME_API_ORIGIN=https://vps-a183fa1c.vps.ovh.net/cem-itx`. Il fonctionne sans cet ordinateur ni Quick Tunnel.

La configuration [deploy/vps/compose.yaml](deploy/vps/compose.yaml) utilise le réseau existant `gamepanel-edge` et le proxy Traefik du panneau OVH. Seules les routes `/cem-itx/api/` sont dirigées vers le jeu. Le certificat HTTPS est géré par ce proxy. Le conteneur redémarre automatiquement avec Docker et conserve ses données dans `/opt/cem-itx/data` : modèle normalisé, vocabulaire, liste de mots, base SQLite et clé de session.

Commandes de gestion sur le VPS :

```bash
sudo docker compose -f /opt/cem-itx/deploy/vps/compose.yaml ps
sudo docker compose -f /opt/cem-itx/deploy/vps/compose.yaml logs --tail 100 game
sudo docker compose -f /opt/cem-itx/deploy/vps/compose.yaml restart game
# Après transfert des fichiers modifiés :
sudo docker compose -f /opt/cem-itx/deploy/vps/compose.yaml up -d --build
```

Le répertoire de données appartient à l’utilisateur du conteneur (UID/GID 10001). Sauvegarder la base avec l’API de sauvegarde SQLite pendant que le jeu tourne ; conserver également `secret.key`, qui permet de retrouver les parties associées aux cookies existants. Les données sont exclues des images Docker et du dépôt Git.

### Alternative : connexion au serveur de cet ordinateur

`connect-online.ps1` permet de revenir à un serveur sur ce PC et remplace la connexion au VPS dans Cloudflare. Après installation des dépendances, de `cloudflared` dans `%LOCALAPPDATA%\CemITX\tools\cloudflared.exe` et authentification de Wrangler, lancer depuis PowerShell :

```powershell
.\connect-online.ps1
```

Le script démarre Waitress sur `127.0.0.1:5001` en arrière-plan si nécessaire, ouvre un tunnel HTTPS et configure `GAME_API_ORIGIN` pour le Worker `c-mitx`. Les processus continuent après fermeture du terminal. Il réutilise un tunnel existant qui répond encore. Les journaux et l’état de connexion se trouvent dans `artifacts`, exclu de Git.

Cet ordinateur doit rester allumé et connecté. L’adresse du Quick Tunnel est temporaire et change après son arrêt ; relancer le script reconnecte le Worker. Pour une disponibilité permanente, utiliser un serveur toujours actif et un tunnel permanent. [Documentation des Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## Alternative : Cloudflare Pages

Pour un projet de type Pages (distinct d’un projet Workers) :

- Commande de build : `exit 0` (aucune compilation nécessaire).
- Répertoire de sortie : `static`.
- Répertoire racine du projet : laisser vide si le dépôt contient directement ce projet.

`index.html`, `style.css` et `app.js` sont dans le même dossier ; les liens relatifs fonctionnent sur Pages et avec Flask. Après avoir poussé les modifications, redéployer le site.

Le fichier `static/_worker.js` assure le relais des routes `/api/game` et `/api/guess` vers le serveur Python. `static/_routes.json` limite son exécution à l’API. Les cookies de session sont conservés sur le domaine du site, et les réponses de jeu ne sont pas mises en cache.

**Configuration nécessaire pour activer le formulaire :**

1. Démarrer le serveur Python avec les fichiers préparés dans `data`. Il doit rester actif et être accessible en HTTPS, directement ou via un Cloudflare Tunnel permanent. Vérifier que son adresse publique suivie de `/api/game` renvoie du JSON.
2. Dans Cloudflare, ouvrir **Workers & Pages → votre projet → Settings → Variables and Secrets**. Ajouter `GAME_API_ORIGIN`, avec l’origine publique du serveur, par exemple `https://jeu-api.votre-domaine.fr`. Ne pas ajouter `/api` ni utiliser l’adresse du site Pages lui-même ou `127.0.0.1`. Configurer séparément l’environnement de production et les aperçus si utilisés.
3. Redéployer le site avec le contenu de `static`, y compris `_worker.js` et `_routes.json`. Pour une intégration Git, pousser aussi ces fichiers dans le dépôt connecté.
4. Ouvrir `/api/game` sur le domaine Pages : la réponse doit être du JSON avec `day` et `attempts`. Recharger la page puis proposer un mot ; l’essai doit rester après actualisation.

Pages exécute le relais JavaScript, mais ne lance pas `app.py` ni le modèle Python. Sans serveur public et sans `GAME_API_ORIGIN`, le relais renvoie une erreur de configuration (503). Ne pas publier le dossier racine du dépôt : il contient les données et peut contenir la clé et la base de jeu.

Documentation : [mode avancé Pages](https://developers.cloudflare.com/pages/functions/advanced-mode/), [variables d’environnement](https://developers.cloudflare.com/pages/functions/bindings/).

## Fonctionnement

### Comptes joueurs

Le formulaire « Créer un compte / Se connecter » demande uniquement un pseudo et un mot de passe. Le pseudo comporte 3 à 24 lettres, chiffres, tirets ou underscores ; son unicité est garantie dans SQLite après normalisation Unicode, sans distinction de majuscules. Le mot de passe comporte 8 à 128 caractères et est stocké sous forme de hachage salé scrypt.

L’inscription conserve l’identité et les essais de l’invité. La connexion sur un autre appareil retrouve les parties du compte ; elle ne fusionne pas les essais de l’invité avec ceux du compte. La déconnexion ouvre une nouvelle session invitée. Aucun e-mail, récupération de mot de passe ni classement public par pseudo n’est ajouté à ce stade.

Les comptes sont dans `data/games.sqlite3`, déjà exclu de Git. La table est créée au démarrage sans supprimer les parties existantes. Déployer ensemble le serveur Python et les fichiers `static` pour activer les nouvelles routes `/api/account*`. Les modifications de compte sont protégées par un jeton CSRF ; les tentatives sont limitées à 10 par pseudo sur 15 minutes.

- Même mot pour tous les joueurs de cette instance, renouvelé à minuit **Europe/Paris**, avec gestion des changements d’heure.
- Mot choisi de façon déterministe parmi les noms singuliers et adjectifs masculins singuliers de `data/targets.txt` présents dans le modèle. La liste peut être enrichie ; sa modification change la sélection quotidienne après redémarrage.
- Température = 100 × similarité cosinus. Pour les mots ayant plusieurs catégories grammaticales, la meilleure similarité est retenue ; les catégories du secret sont limitées aux noms et adjectifs.
- Les 999 voisins les plus proches sont classés de 999 à 1 ‰. Le secret vaut 1 000 ‰ et 100 °C. Les ex æquo sont départagés alphabétiquement. Les voisins incluent aussi des verbes et adverbes lemmatisés.
- Accents conservés, casse ignorée, Unicode normalisé. Les mots inconnus et doublons ne consomment pas d’essai.
- Essais en SQLite côté serveur. Un cookie signé, valable un an, identifie chaque navigateur. En mode invité, effacer ce cookie ou changer de navigateur crée un nouveau joueur. Avec un compte, la connexion retrouve les parties sur les autres appareils.
- Classement par ordre de découverte sur cette instance, indépendant du nombre d’essais. Une transaction SQLite sérialise les victoires simultanées.
- Tri par température ou dernier essai, règles intégrées, compteur jusqu’à minuit, partage sans révéler le mot.
- Choix du thème classique ou sombre dans l’en-tête, mémorisé pour ce navigateur.

Le modèle exact, le filtrage et la sélection des mots du site original ne sont pas déterminés par les ressources fournies. Cette application reproduit les mécaniques décrites, avec ses propres mots, scores et classement. Son interface est originale.

## Vérification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check static/app.js
node tests/cloudflare-check.mjs
# Avec le serveur actif et Chrome installé :
node tests/browser-check.cjs
```

Les tests utilisent un modèle synthétique exclusivement comme fixture ; le jeu utilise les vecteurs officiels.

Le serveur Flask intégré convient à un usage local. Pour héberger l’application, utiliser un serveur WSGI et HTTPS, activer les cookies sécurisés et conserver la base, les caches et `data/secret.key`. `CEMENTIX_SECRET` permet de fournir une clé stable. Ne pas servir le répertoire `data` comme fichiers statiques.

## Attribution des données

**frWac_postag_no_phrase_700_skip_cut50.bin**, skip-gram, 700 dimensions, corpus frWac (1,6 milliard de mots), lemmatisé et annoté grammaticalement.

Jean-Philippe Fauconnier, *French Word Embeddings*, 2015 : https://fauconnier.github.io/#data. Licence **CC BY 3.0** : https://creativecommons.org/licenses/by/3.0/. MD5 : https://embeddings.net/embeddings/md5sum.txt. L’attribution figure également dans l’application.

Jeu de référence : https://cemantix.certitudes.org.
