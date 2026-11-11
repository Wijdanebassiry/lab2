## Payments Service (port 8085)

Dossier : `payments-service` | Base URL : `http://localhost:8085`

Docs : `http://localhost:8085/docs` | OpenAPI : `payments-service/payment-openapi.json`

Statut : tous les endpoints sont implémentés et testés (11 tests automatiques + tests manuels Swagger).

### POST /api/payments

Requête : `{ "orderId": "order-demo-001", "method": "CARD" }` (`method` = `CARD` ou `CASH`, défaut `CARD`).

`orderId` est une chaîne (pas forcément un UUID). Le montant n'est pas envoyé : Payments lit `total` chez Orders.

Réponse 201 :

```json
{
  "id": "uuid",
  "orderId": "order-demo-001",
  "amount": 250.0,
  "method": "CARD",
  "status": "SUCCESS",
  "createdAt": "2026-11-06T14:00:00Z"
}
```

Erreurs, au format `{ "message": "...", "detail": "..." }` :

| Code | Message |
|---|---|
| 404 | Order not found. |
| 409 | Order is not awaiting payment. / Payment already attempted for this order. |
| 402 | Payment declined: `<raison>` |
| 401 / 403 | Not authorized to access this order. (renvoyé quand Orders refuse le token) |
| 503 | Orders service unavailable. / Orders service error. / Could not update order status. / Payment provider unavailable. |
| 422 | Body invalide (`orderId` manquant) |

### GET /api/payments/order/{orderId}

200 avec le paiement le plus récent, ou 404 « Payment not found. » s'il n'y en a pas.

### GET /api/payments

200 avec la liste des paiements.

### GET /health

`{ "status": "UP", "service": "payment" }`

Valeurs de `status` : `SUCCESS`, `FAILED`, `REFUNDED`, `PENDING`.

### Dépendance : Payments appelle Orders (`ORDERS_URL`, défaut `http://localhost:8084`)

- `GET /api/orders/{id}` doit renvoyer au minimum `{ "id", "total" (nombre), "status": "PENDING_PAYMENT" }`, et 404 si la commande n'existe pas.
- `PATCH /api/orders/{id}/status` avec `{ "status": "PAID" }`, accepté depuis `PENDING_PAYMENT`, répond 200.
- Si la requête contient `Authorization: Bearer <token>`, Payments le transmet tel quel à Orders (GET et PATCH). Sans token, aucun en-tête n'est envoyé. Un 401/403 d'Orders est renvoyé tel quel.

### Cas de test

`method` = `TEST_DECLINE` (402), `TEST_TIMEOUT` (503) ; total > 50000 refusé (402).


## Inventory Service (port 8083)

Dossier : `inventory-service` | Base URL : `http://localhost:8083`

Docs : `http://localhost:8083/docs`

Statut : tous les endpoints sont implémentés et testés (9 tests automatiques + tests manuels Swagger).

Les `productId` sont les mêmes que ceux du frontend et du Catalog (1 à 6). Ils sont acceptés en nombre ou en chaîne, et renvoyés en chaîne.
Le stock disponible est renvoyé dans le champ `stock` (lu par le frontend : `data.stock`).

### GET /api/inventory

200 : `[{ "productId": "1", "stock": 12 }]`

### GET /api/inventory/{productId}

200 : `{ "productId": "1", "stock": 12 }`, ou 404 « Product not found. »

### POST /api/inventory/check

Requête : `{ "items": [{ "productId": "1", "quantity": 2 }] }`. Ne modifie rien.

Réponse 200 : `{ "available": true, "unavailable": [] }`

### POST /api/inventory/reserve

Même requête. **Atomique** : tous les produits sont réservés, ou aucun. Les doublons de `productId` sont fusionnés.

- 200 : `{ "success": true }`
- 409 : `{ "message": "Insufficient stock.", "detail": "...", "unavailable": [{ "productId": "2", "requested": 5, "available": 1 }] }` (le stock n'est pas modifié)
- 422 : body invalide, au format `{ "message": "Invalid request body.", "detail": "..." }`

### POST /api/inventory/release

Même requête. Remet le stock (annulation de commande). Réponse 200 : `{ "success": true }`

### GET /health

`{ "status": "UP", "service": "inventory" }`

### Appelant : Orders (`INVENTORY_URL`, défaut `http://localhost:8083`)

Orders appelle `reserve` à la création de la commande (un 409 signifie que la commande est refusée) et `release` à l'annulation.


## Catalog Service (port 8082)

Dossier : `catalog-service` | Base URL : `http://localhost:8082`

Stack : Node.js + Express 5 + SQLite (`catalog.db`)

Statut : tous les endpoints sont implémentés et testés (9 tests automatiques avec `npm test`). Service en lecture seule, sans authentification.

Les `id` sont les mêmes que ceux du frontend et d'Inventory (1 à 6). Ici ils sont renvoyés en **nombre** (Inventory les renvoie en chaîne).

### Objet product

```json
{
  "id": 1,
  "name": "ThinkPad Laptop",
  "category": "Electronics",
  "price": 8499.0,
  "image": "",
  "description": "Business laptop"
}
```

`price` est un nombre. `image` peut être une chaîne vide.

### GET /products

200 : tableau de tous les produits.

### GET /products/:id

200 : l'objet product.

### Erreurs

Format `{ "message": "..." }`.

| Code | Message | Cas |
|---|---|---|
| 400 | Invalid product id. | id de plus de 100 caractères |
| 400 | Malformed JSON body. | corps JSON mal formé |
| 404 | Product not found. | id inconnu |
| 404 | Not found | route inconnue |
| 500 | Internal server error | erreur inattendue |

### CORS

Seules les origines de `FRONTEND_ORIGIN` sont autorisées, méthode `GET` uniquement.

### Configuration

Variables d'environnement obligatoires : `HOST`, `PORT` (8082), `FRONTEND_ORIGIN` (voir `.env.example`).

### Appelants et dépendances

- Catalog n'appelle aucun autre service.
- Le frontend appelle Catalog pour afficher les produits. Le stock disponible vient d'Inventory.


## Auth Service (port 8081)

Dossier : `auth-service` | Base URL : `http://localhost:8081`

Stack : Django + Django REST Framework + SimpleJWT (SQLite)


Statut : tous les endpoints sont implémentés et testés (15 tests automatiques avec `python manage.py test` + tests manuels PowerShell et frontend du professeur avec `AUTH: "rest"`).

### Token

- Format : JWT (HS256), durée de vie 1 jour.
- À envoyer sur les routes protégées : `Authorization: Bearer <token>`.
- Le token contient l'identifiant de l'utilisateur (`user_id`) et la date d'expiration. Il ne contient **ni l'email ni le rôle** : pour les obtenir, appeler `GET /api/auth/me`.
- **Pour vérifier un token, appeler `GET /api/auth/me`** avec le même en-tête. Pas de clé secrète à partager entre services.

### Objet user

```json
{ "id": "user-1", "name": "Demo Customer", "email": "demo@msoa.shop", "role": "CUSTOMER" }
```

`id` est une chaîne (`user-1` pour le compte démo, `user-` suivi de 8 caractères pour les nouveaux comptes) : c'est la valeur à utiliser comme `userId` dans les commandes. `role` vaut `CUSTOMER` ou `ADMIN`. Le mot de passe n'est jamais renvoyé. L'email est stocké en minuscules.

### POST /api/auth/login

Requête : `{ "email": "demo@msoa.shop", "password": "demo123" }` (majuscules et espaces autour de l'email ignorés).

Réponse 200 :

```json
{
  "user": { "id": "user-1", "name": "Demo Customer", "email": "demo@msoa.shop", "role": "CUSTOMER" },
  "token": "<jwt>"
}
```

### POST /api/auth/register

Requête : `{ "name": "Test User", "email": "test@msoa.shop", "password": "test123" }`

Réponse 201 : l'objet user (sans token). Le client doit ensuite appeler `login`.

### POST /api/auth/logout

Token requis. Réponse 204, sans corps. Le token reste valide jusqu'à son expiration (le frontend supprime sa session).

### GET /api/auth/me

Token requis. Réponse 200 : l'objet user (directement, sans enveloppe).

### Erreurs

Format `{ "message": "...", "error": "..." }` (les deux clés ont le même texte ; le frontend lit `message`).

| Code | Message | Endpoint |
|---|---|---|
| 400 | All fields are required. | register |
| 401 | Invalid email or password. | login |
| 401 | Token absent, invalide ou expiré | logout, me |
| 409 | Email already registered. | register |

### Compte de démonstration

`demo@msoa.shop` / `demo123` (id `user-1`), créé avec `python manage.py seed_demo`.

### Appelants et dépendances

- Auth n'appelle aucun autre service.
- Orders, Payments et Shipping valident un token en appelant `GET http://localhost:8081/api/auth/me` avec l'en-tête `Authorization` reçu. Orders utilise `user.id` comme `userId` de la commande.


## Shipping Service (port 8086)

Dossier : `shipping-service` | Base URL : `http://localhost:8086` | Database : `shipping_db`

**Statut :** endpoints REST implémentés. Authentification JWT et synchronisation des statuts avec Orders implémentées.

### Authentification

Toutes les routes Shipping nécessitent un Bearer Token valide dans l'en-tête :

```http
Authorization: Bearer <token>
```

Shipping conserve le header `Authorization` reçu du client et le transmet au service Auth et au service Orders lorsque nécessaire.

- `401 Unauthorized` : token absent ou invalide.
- Le token est vérifié auprès de Auth via `GET /api/auth/me`.

### GET /api/shipments

200 : retourne la liste de toutes les livraisons.

### GET /api/shipments/order/{orderId}

200 : retourne la livraison associée à la commande.

404 : aucune livraison trouvée pour cette commande.

### POST /api/shipments

Requête :

```json
{
  "orderId": "order-demo-001",
  "address": {
    "name": "Demo Customer",
    "address": "123 Main Street",
    "city": "Casablanca"
  }
}
```

- `orderId` est une chaîne de caractères.
- `address.name`, `address.address` et `address.city` sont obligatoires.
- Le montant n'est pas envoyé.
- Le backend génère l'ID et le numéro de suivi (`trackingNumber`).
- Le statut initial est `PREPARING`.
- La création est autorisée uniquement si la commande existe et possède le statut `PAID`.
- Une seule livraison est autorisée par commande.

Réponse 201 : retourne les informations de la livraison créée, notamment `id`, `orderId`, `trackingNumber`, `name`, `address`, `city`, `status`, `createdAt` et `updatedAt`.

### PATCH /api/shipments/{id}/status

Requête :

```json
{ "status": "SHIPPED" }
```

Statuts et transitions autorisés :

- `PREPARING` → `SHIPPED`
- `SHIPPED` → `IN_TRANSIT`
- `IN_TRANSIT` → `DELIVERED`

400 : transition de statut invalide.

404 : livraison introuvable.

Lorsqu'une livraison passe à :

- `SHIPPED` : Shipping appelle `PATCH /api/orders/{orderId}/status` avec `{"status":"SHIPPED"}`.
- `IN_TRANSIT` : aucun changement du statut de la commande dans Orders.
- `DELIVERED` : Shipping appelle `PATCH /api/orders/{orderId}/status` avec `{"status":"DELIVERED"}`.

Le header `Authorization` du client est transmis à Orders.

**Important :** si l'appel PATCH à Orders échoue, Shipping retourne une erreur `502` ou `503` et ne modifie pas le statut de la livraison.

### Format des erreurs

Les erreurs gérées par `GlobalExceptionHandler` utilisent le format :

```json
{ "message": "Error description", "error": "BAD_REQUEST" }
```

Codes HTTP possibles selon le type d'erreur :

| Code | Cas |
|---|---|
| 400 | Données invalides ou transition de statut interdite |
| 401 | Token absent ou invalide |
| 404 | Livraison ou commande introuvable |
| 409 | Livraison déjà créée pour cette commande |
| 502 | Erreur de communication avec Orders |
| 503 | Orders Service indisponible |

### Dépendances : Shipping appelle

- **Auth** (`AUTH_URL`, défaut `http://localhost:8081`) : validation du Bearer Token via `GET /api/auth/me`.
- **Orders** (`ORDERS_URL`, défaut `http://localhost:8084`) :
  - `GET /api/orders/{orderId}` : vérification de l'existence de la commande et de son statut `PAID` avant la création d'une livraison.
  - `PATCH /api/orders/{orderId}/status` : synchronisation du statut de la commande lors des transitions vers `SHIPPED` et `DELIVERED`.

### Intégration et tests

- Vérification du paiement auprès d'Orders : implémentée.
- Transmission du token client à Auth et Orders : implémentée.
- Synchronisation des statuts Shipping/Orders : implémentée.
- Tests unitaires et tests applicatifs : 10 tests exécutés, 0 échec, 0 erreur.
- L'intégration réelle entre les services reste à valider dans l'environnement de déploiement.


## Orders Service (port 8084)

Dossier : `orders-service` | Base URL : `http://localhost:8084`

**Stack :** Node.js + Express + SQLite (`better-sqlite3`).

**Database :** `msoa_sqlite_databases/orders/orders.db`

La base de données est initialisée à l'aide de `schema.sql` et `seed.sql` via la commande `npm run init-db`.

### Authentification

Toutes les routes Orders, sauf `GET /` (health check), nécessitent un Bearer Token valide.

Orders valide le token auprès du service Auth via `GET /api/auth/me`.

L'identifiant de l'utilisateur authentifié (`user.id`) est utilisé comme `userId`. Le client ne doit pas envoyer ni choisir `userId`.

### Endpoints

- `GET /` : vérification de disponibilité du service.
- `GET /api/orders` : retourne les commandes de l'utilisateur authentifié. Un ADMIN peut consulter toutes les commandes.
- `GET /api/orders/{id}` : retourne une commande appartenant à l'utilisateur authentifié. Un ADMIN peut consulter les détails de toutes les commandes.
- `POST /api/orders` : crée une commande pour l'utilisateur authentifié.
- `PATCH /api/orders/{id}/status` : met à jour le statut d'une commande appartenant à l'utilisateur authentifié, selon les transitions autorisées.
- `POST /api/orders/{id}/cancel` : annule une commande éligible appartenant à l'utilisateur authentifié.

**Remarque :** les droits ADMIN concernent uniquement la lecture des commandes. La modification du statut et l'annulation restent réservées au propriétaire de la commande.

### Création d'une commande

Requête `POST /api/orders` :

```json
{
  "customer": {
    "name": "Demo Customer",
    "address": "123 Main Street",
    "city": "Casablanca"
  },
  "items": [
    { "productId": 1, "quantity": 2 }
  ]
}
```

Lors de la création :

- Les informations et les prix des produits sont récupérés auprès de Catalog.
- Les quantités demandées sont validées.
- Le stock est réservé auprès d'Inventory.
- Le total de la commande est calculé par Orders.
- La commande et ses articles sont enregistrés dans SQLite.

Statut initial : `PENDING_PAYMENT`.

### Statuts et transitions

Statuts possibles :

- `PENDING_PAYMENT`
- `PAID`
- `SHIPPED`
- `DELIVERED`
- `CANCELLED`

Transitions autorisées par l'endpoint de mise à jour :

`PENDING_PAYMENT` → `PAID` → `SHIPPED` → `DELIVERED`.

`DELIVERED` et `CANCELLED` sont des statuts finaux.

La mise à jour du statut est soumise aux transitions autorisées. L'endpoint ne réalise pas lui-même une vérification auprès d'un service de paiement.

### Annulation d'une commande

L'annulation est possible uniquement lorsque la commande est dans l'état `PENDING_PAYMENT` ou `PAID`.

Avant l'annulation :

- Orders vérifie l'état de livraison auprès de Shipping.
- L'annulation est refusée si la livraison a déjà dépassé l'état `PREPARING`.
- Le stock réservé est libéré auprès d'Inventory.
- Le statut de la commande passe à `CANCELLED`.

En cas d'échec après la libération du stock, Orders tente de réserver à nouveau les articles.

### Dépendances : Orders appelle

- **Auth** (`AUTH_URL`, défaut `http://127.0.0.1:8081`) : validation du Bearer Token via `GET /api/auth/me`.
- **Catalog** (`CATALOG_URL`, défaut `http://127.0.0.1:8082`) : récupération des informations et des prix des produits via `/products/{productId}`.
- **Inventory** (`INVENTORY_URL`, défaut `http://127.0.0.1:8083`) : réservation et libération du stock.
- **Shipping** (`SHIPPING_URL`, défaut `http://127.0.0.1:8086`) : vérification de l'état de livraison lors d'une annulation via `GET /api/shipments/order/{orderId}`.

### Tests

Pour exécuter les tests, ouvrir un terminal dans le dossier `orders-service` et lancer :

```bash
npm test
```

Les tests couvrent :

- Le rejet des requêtes sans token et avec un token invalide.
- L'isolation des commandes par utilisateur.
- L'accès en lecture de l'ADMIN à toutes les commandes et à leurs détails.
- La création d'une commande avec succès.
- Le rejet d'un corps de requête invalide.
- Le refus d'une commande lorsque le stock est insuffisant.
- Les transitions de statut autorisées et interdites.
- L'annulation des commandes en attente de paiement ou déjà payées.
- Le refus d'annulation lorsqu'une livraison est déjà expédiée.

Résultat : 14 tests réussis, 0 échec.

### Objet order

```json
{
  "id": "5b3c1c0e-…",
  "userId": "user-1",
  "customer": {
    "name": "Demo Customer",
    "address": "123 Main Street",
    "city": "Casablanca"
  },
  "total": 199,
  "status": "PENDING_PAYMENT",
  "createdAt": "2026-11-01T10:00:00.000Z",
  "items": [
    {
      "productId": 2,
      "name": "Wireless Mouse",
      "price": 199,
      "quantity": 1
    }
  ]
}
```

`id` est une chaîne (UUID). Le `total` est calculé par Orders à partir des prix du Catalog.

### Codes d'erreur

Format `{ "message": "..." }` (les erreurs d'authentification ont aussi la clé `error`).

| Code | Cas |
|---|---|
| 400 | Body invalide, transition de statut interdite ou commande non annulable |
| 401 | Token absent, invalide ou expiré |
| 403 | La commande appartient à un autre utilisateur |
| 404 | Commande ou produit introuvable |
| 409 | Stock insuffisant (création) ou livraison déjà expédiée (annulation) |
| 502 | Informations produit invalides reçues du Catalog |
| 503 | Service Auth indisponible |

### Appelants

- **Payments** : `GET /api/orders/{id}` puis `PATCH /api/orders/{id}/status` (`PAID`), avec le token du client.
- **Shipping** : `GET /api/orders/{id}` (vérifier `PAID`), puis `PATCH /api/orders/{id}/status` (`SHIPPED`, `DELIVERED`), avec le token du client.

### Décisions d'intégration

- Sur l'annulation, Orders transmet à Shipping l'en-tête `Authorization` reçu du client (Shipping exige un token).
- Shipping met à jour la commande : livraison `SHIPPED` → commande `SHIPPED`, livraison `DELIVERED` → commande `DELIVERED` (`IN_TRANSIT` ne change rien).
