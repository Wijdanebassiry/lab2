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

The Orders service checks stock availability through gRPC (low latency, typed contract).
REST routes are unchanged and remain available.

Contract: `proto/inventory.proto`. One operation:

| RPC | Request | Response |
|---|---|---|
| `InventoryService/CheckAvailability` | `items: [{ productId, quantity }]` | `available`, `unavailable: [{ productId, requested, availableQuantity }]` |

Status codes: `NOT_FOUND` for an unknown product, `INVALID_ARGUMENT` for an empty list
or a quantity <= 0. `productId` is a string. `reserve` and `release` stay on REST.

Run the server (separate terminal, same folder as the REST service):

```bash
python -m app.grpc_server
```

Test with grpcurl:

```bash
grpcurl -plaintext -proto proto/inventory.proto -d '{"items":[{"productId":"3","quantity":3}]}' localhost:50051 inventory.InventoryService/CheckAvailability
```

The generated code is in `app/grpc_gen/`. After editing the `.proto`, regenerate it with
`python -m grpc_tools.protoc -I proto --python_out=app/grpc_gen --grpc_python_out=app/grpc_gen proto/inventory.proto`
and change the import in `inventory_pb2_grpc.py` to `from . import inventory_pb2 as inventory__pb2`.

## Tests

```bash
python -m pytest -q
```

9 automated tests cover reserve, atomicity, duplicates, numeric IDs, release, check and errors.

## Configuration

| Variable | Default |
|---|---|
| `DATABASE_URL` | `sqlite:///./data/inventory.db` |
| `GRPC_PORT` | `50051` |
