# Inventory Service (port 8083)

Microservice that manages product stock. Built with FastAPI and SQLite.
It owns the stock data only; product details (name, price, image) live in the Catalog service.

## Run locally

```bash
python -m venv venv
venv\Scripts\activate            # Windows (cmd)
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --port 8083 --reload
```

Swagger docs: http://localhost:8083/docs

On first start the database (`data/inventory.db`) is created and seeded with the
6 products of the frontend (IDs 1 to 6). To reset the stock, stop the service and delete the `data` folder.

## Endpoints

| Method | URL | Description |
|---|---|---|
| GET | /api/inventory | list stock of all products |
| GET | /api/inventory/{productId} | stock of one product (404 if unknown) |
| POST | /api/inventory/check | check availability, does not modify stock |
| POST | /api/inventory/reserve | reserve stock, all-or-nothing |
| POST | /api/inventory/release | give stock back (cancelled order) |
| GET | /health | health check |

Body of check / reserve / release: `{ "items": [{ "productId": "1", "quantity": 2 }] }`

### Responses

| Endpoint | Success response |
|---|---|
| `GET /api/inventory` | `[{ "productId": "1", "stock": 12 }]` |
| `GET /api/inventory/{productId}` | `{ "productId": "1", "stock": 12 }` |
| `POST /api/inventory/check` | `{ "available": true, "unavailable": [] }` |
| `POST /api/inventory/reserve` | `{ "success": true }` |
| `POST /api/inventory/release` | `{ "success": true }` |

The field is called `stock` because the React frontend reads `data.stock`.

`productId` can be sent as a number or a string; it is returned as a string.

`reserve` is atomic: if one product is short, nothing is reserved and the service
answers 409 with the list of unavailable products. Duplicate product IDs in a
request are merged.

Errors are returned as `{ "message": "...", "detail": "..." }`:

| Code | Meaning |
|---|---|
| 404 | Product not found |
| 409 | Insufficient stock |
| 422 | Invalid request body |

## Tests

```bash
python -m pytest -q
```

9 automated tests cover reserve, atomicity, duplicates, numeric IDs, release, check and errors.

## Configuration

| Variable | Default |
|---|---|
| `DATABASE_URL` | `sqlite:///./data/inventory.db` |
