Markdown
# Catalog Service (port 8082)

Microservice qui expose le catalogue produits. Stack : Node.js 22, Express 5, SQLite (`catalog.db`).
Il gère uniquement les informations produit (nom, prix, image…) ; le stock est dans Inventory.

catalog.db n'est pas versionné : il est créé et rempli (6 produits) au premier démarrage. Les tests utilisent une base temporaire.

## Lancer en local

cd catalog-service
npm install
cp .env.example .env        # Windows (cmd) : copy .env.example .env
npm start                 # ou npm run dev (nodemon)


> **Le fichier `.env` est obligatoire.** Sans lui, `PORT`, `HOST` et `FRONTEND_ORIGIN` sont vides et le
> service plante au démarrage. `.env` n'est pas versionné (il est dans `.gitignore`) : chacun copie
> `.env.example`.

## Configuration

| Variable | Exemple | Rôle | 
| ----- | ----- | ----- | 
| `HOST` | `127.0.0.1` | Adresse d'écoute | 
| `PORT` | `8082` | Port d'écoute | 
| `FRONTEND_ORIGIN` | `http://localhost:5173,http://127.0.0.1:5173` | Origines autorisées par CORS, séparées par des virgules | 
| `DB_PATH` | *(optionnel)* | Chemin de la base SQLite (défaut : `catalog.db` du dossier) | 
| `RATE_EUR` | `10.87` | Taux de conversion MAD vers EUR (par défaut : `10.87`) | 
| `RATE_USD` | `10.0` | Taux de conversion MAD vers USD (par défaut : `10.0`) | 

## Endpoints

### API v1

| Méthode | URL | Description | 
| ----- | ----- | ----- | 
| GET | /products | liste de tous les produits (prix simple en MAD) | 
| GET | /products/:id | un produit par ID (prix simple en MAD, 404 s'il n'existe pas) | 

### API v2 (Structured Price & Multi-Currency)

| Méthode | URL | Description | 
| ----- | ----- | ----- | 
| GET | /v2/products | liste des produits avec prix structuré ({ amount, currency }). Paramètre optionnel ?currency=MAD, EUR ou USD (MAD par défaut) | 
| GET | /v2/products/:id | un produit avec prix structuré. Même paramètre ?currency= | 

Erreurs au format `{ "message": "..." }` : 400 (id ou devise invalide), 404 (produit ou route inconnue), 500.
Le détail est dans `CONTRACTS.md`.

## Tests

npm test


19 tests automatiques (`node --test` + supertest) couvrant l'API v1 et l'API v2 (liste, champs du contrat, conversion multi-devises MAD/EUR/USD, validation des devises non supportées, gestion des erreurs 400/404, tentative d'injection SQL, en-têtes helmet et CORS). Ils travaillent sur une copie temporaire ou la base de données, la structure globale n'est pas altérée.