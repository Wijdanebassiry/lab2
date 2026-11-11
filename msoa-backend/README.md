# MSOA Backend

Backend e-commerce en microservices. Les contrats d'API (routes, formats, erreurs) sont dans [`CONTRACTS.md`](CONTRACTS.md).

| Service | Port | Techno | Dossier |
|---|---|---|---|
| Auth | 8081 | Django + DRF + SimpleJWT | `auth-service` |
| Catalog | 8082 | Node.js + Express + SQLite | `catalog-service` |
| Inventory | 8083 | FastAPI + SQLite | `inventory-service` |
| Orders | 8084 | Node.js + Express + SQLite | `orders-service` |
| Payments | 8085 | FastAPI + SQLite | `payments-service` |
| Shipping | 8086 | Spring Boot + MySQL | `shipping-service` |

## Flux principal
1. Le client se connecte (Auth) et reçoit un token JWT.
2. Il crée une commande (Orders) : prix lus chez Catalog, stock réservé chez Inventory.
3. Il paie (Payments) : le montant est lu chez Orders, la commande passe à `PAID`.
4. Une livraison est créée (Shipping) pour une commande `PAID` ; ses changements de statut mettent à jour la commande.

Les services protégés valident le token avec `GET /api/auth/me` (Auth).

## Lancer les services (sans Docker)
Un terminal par service, depuis la racine du dépôt. Prérequis : Python 3.12, Node.js 22, Java 21 et MySQL 8 (Shipping uniquement).

| Service | Commandes |
|---|---|
| Auth (8081) | `cd auth-service && pip install -r requirements.txt && python manage.py migrate && python manage.py seed_demo && python manage.py runserver 8081` |
| Catalog (8082) | `cd catalog-service && npm ci && cp .env.example .env && node server.js` |
| Inventory (8083) | `cd inventory-service && pip install -r requirements.txt && uvicorn app.main:app --port 8083` |
| Orders (8084) | `cd orders-service && npm ci && npm run init-db && npm start` |
| Payments (8085) | `cd payments-service && pip install -r requirements.txt && uvicorn app.main:app --port 8085` |
| Shipping (8086) | créer la base : `CREATE DATABASE shipping_db;` puis `cd shipping-service && ./mvnw spring-boot:run` |

Ordre conseillé : Auth, Catalog, Inventory, Orders, Payments, Shipping.
Shipping utilise MySQL (`root`, mot de passe vide par défaut ; modifiable par `DB_URL`, `DB_USERNAME`, `DB_PASSWORD`).
Docs interactives : Payments `http://localhost:8085/docs`, Inventory `http://localhost:8083/docs`.

## Lancer les tests
```bash
cd auth-service      && python manage.py test        # 15 tests
cd payments-service  && python -m pytest             # 11 tests
cd inventory-service && python -m pytest             # 9 tests
cd catalog-service   && npm ci && npm test           # 9 tests
cd orders-service    && npm ci && npm test           # 3 tests
cd shipping-service  && ./mvnw test                  # Java 21
```

## Base de données Orders
`orders.db` n'est pas versionnée. Elle est créée par `npm run init-db --prefix orders-service` (schema.sql + seed.sql).

## Contribuer
Ne jamais pousser sur `main`. Créer une branche, puis ouvrir une Pull Request relue par un autre membre :
```bash
git checkout main && git pull origin main
git checkout -b feature/ma-branche
git add . && git commit -m "message clair"
git push -u origin feature/ma-branche
```
Ne modifier que le dossier de son service, et uniquement sa propre section dans `CONTRACTS.md`.
