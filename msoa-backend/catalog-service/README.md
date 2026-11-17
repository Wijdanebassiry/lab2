# Catalog Service (port 8082)

Microservice qui expose le catalogue produits. Stack : Node.js 22, Express 5, SQLite (`catalog.db`).
Il gère uniquement les informations produit (nom, prix, image…) ; le stock est dans Inventory.

## Lancer en local

```bash
cd catalog-service
npm install
cp .env.example .env      # Windows (cmd) : copy .env.example .env
npm start                 # ou npm run dev (nodemon)
```

> **Le fichier `.env` est obligatoire.** Sans lui, `PORT`, `HOST` et `FRONTEND_ORIGIN` sont vides et le
> service plante au démarrage. `.env` n'est pas versionné (il est dans `.gitignore`) : chacun copie
> `.env.example`.

## Configuration

| Variable | Exemple | Rôle |
|---|---|---|
| `HOST` | `127.0.0.1` | Adresse d'écoute |
| `PORT` | `8082` | Port d'écoute |
| `FRONTEND_ORIGIN` | `http://localhost:5173,http://127.0.0.1:5173` | Origines autorisées par CORS, séparées par des virgules |
| `DB_PATH` | *(optionnel)* | Chemin de la base SQLite (défaut : `catalog.db` du dossier) |

## Endpoints

| Méthode | URL | Description |
|---|---|---|
| GET | /products | liste de tous les produits |
| GET | /products/:id | un produit (404 s'il n'existe pas) |

Erreurs au format `{ "message": "..." }` : 400 (id invalide), 404 (produit ou route inconnue), 500.
Le détail est dans `CONTRACTS.md`.

## Tests

```bash
npm test
```

9 tests automatiques (`node --test` + supertest) : liste, champs du contrat, produit par id, 404, 400,
tentative d'injection SQL, en-têtes helmet et CORS. Ils travaillent sur une copie temporaire de
`catalog.db`, la vraie base n'est pas modifiée.
