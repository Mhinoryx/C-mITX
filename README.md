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

## Déploiement du jeu sur Cloudflare Pages

Pour publier le dépôt via Pages :

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

- Même mot pour tous les joueurs de cette instance, renouvelé à minuit **Europe/Paris**, avec gestion des changements d’heure.
- Mot choisi de façon déterministe parmi les noms singuliers et adjectifs masculins singuliers de `data/targets.txt` présents dans le modèle. La liste peut être enrichie ; sa modification change la sélection quotidienne après redémarrage.
- Température = 100 × similarité cosinus. Pour les mots ayant plusieurs catégories grammaticales, la meilleure similarité est retenue ; les catégories du secret sont limitées aux noms et adjectifs.
- Les 999 voisins les plus proches sont classés de 999 à 1 ‰. Le secret vaut 1 000 ‰ et 100 °C. Les ex æquo sont départagés alphabétiquement. Les voisins incluent aussi des verbes et adverbes lemmatisés.
- Accents conservés, casse ignorée, Unicode normalisé. Les mots inconnus et doublons ne consomment pas d’essai.
- Essais en SQLite côté serveur. Un cookie signé, valable un an, identifie chaque navigateur. Effacer ce cookie ou changer de navigateur crée un nouveau joueur ; aucune synchronisation entre appareils.
- Classement par ordre de découverte sur cette instance, indépendant du nombre d’essais. Une transaction SQLite sérialise les victoires simultanées.
- Tri par température ou dernier essai, règles intégrées, compteur jusqu’à minuit, partage sans révéler le mot.

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
