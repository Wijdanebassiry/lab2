# Orders Microservice

Microservice responsible for creating, retrieving, updating and cancelling customer orders.

## Requirements

- Node.js 22 or compatible version
- npm

## Installation

From the project root:

```bash
npm install --prefix orders-service
```

## Database Initialization

The database is stored in `msoa_sqlite_databases/orders/orders.db`.

To initialize the database if it does not exist:

```bash
npm run init-db --prefix orders-service
```

The initialization script creates the database using `schema.sql` and `seed.sql`. If the database already exists, initialization is skipped to preserve existing data.

## Run the Service

```bash
npm start --prefix orders-service
```

Default port: `8084`.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| PORT | 8084 | Orders service port |
| AUTH_URL | http://127.0.0.1:8081 | Authentication service |
| CATALOG_URL | http://127.0.0.1:8082 | Catalog service |
| INVENTORY_URL | http://127.0.0.1:8083 | Inventory service |
| SHIPPING_URL | http://127.0.0.1:8086 | Shipping service |

## Authentication

All order routes require:

```http
Authorization: Bearer <token>
```

The token is validated through the Auth service using `GET /api/auth/me`. The authenticated user's ID is used as the order's `userId`.

## Order Statuses

- `PENDING_PAYMENT`
- `PAID`
- `SHIPPED`
- `DELIVERED`
- `CANCELLED`

Orders communicates with Catalog to retrieve product information and Inventory to reserve or release stock.