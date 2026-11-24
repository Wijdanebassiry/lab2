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


## gRPC (port 50051)

Orders reserves and releases stock through gRPC (low latency, typed contract). The REST
API (port 8083) is unchanged and remains available for the frontend.

Contract: `contracts/inventory.proto` (package `inventory.v1`, service `Inventory`).
`proto/inventory.proto` is an exact copy of it: there must be one contract only.

| RPC | Request | Response | Effect |
|---|---|---|---|
| `CheckAvailability` | `StockRequest { items: [{ product_id, quantity }] }` | `{ available, unavailable[] }` | modifies nothing |
| `Reserve` | `StockRequest` | `{ success, unavailable[] }` | all or nothing; `success = false` if the stock is insufficient |
| `Release` | `StockRequest` | `{ success }` | puts the stock back |

Errors: `INVALID_ARGUMENT` for an empty `items`, an empty `product_id` or a quantity <= 0.
An unknown product is reported in `unavailable` (`available = 0`), as in REST.

The gRPC server starts with the API (lifespan in `app/main.py`, after `seed()`) and stops
with it. Port: `GRPC_PORT` (default `50051`). No separate process is needed.

After a change of the contract, copy `contracts/inventory.proto` to `proto/inventory.proto`,
then regenerate the code (`app/grpc_gen`):

```bash
python scripts/gen_grpc.py
```

Test with grpcurl:

```bash
grpcurl -plaintext -proto proto/inventory.proto 127.0.0.1:50051 list
grpcurl -plaintext -proto proto/inventory.proto -d '{"items":[{"product_id":"3","quantity":2}]}' 127.0.0.1:50051 inventory.v1.Inventory/Reserve
```
## Tests

```bash
python -m pytest -q
```

22 automated tests: 9 for REST (reserve, atomicity, duplicates, numeric IDs, release, check, errors) and 13 for gRPC (CheckAvailability, Reserve, Release, insufficient stock, invalid arguments).

## Configuration

| Variable | Default |
|---|---|
| `DATABASE_URL` | `sqlite:///./data/inventory.db` |
| `GRPC_PORT` | `50051` |
