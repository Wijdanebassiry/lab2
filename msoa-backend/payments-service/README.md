# Payment Service (port 8085)

Microservice that processes payments for orders. Built with FastAPI and SQLite.
It owns the payment data only; order totals and statuses are read from the Orders service.

## Run locally

```bash
python -m venv venv
venv\Scripts\activate            # Windows (cmd)
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --port 8085 --reload
```

Swagger docs: http://localhost:8085/docs | OpenAPI file: `payment-openapi.json`

## Endpoints

| Method | URL | Description |
|---|---|---|
| POST | /api/payments | pay an order, body `{ "orderId": "...", "method": "CARD" }` |
| GET | /api/payments/order/{orderId} | payment of an order (404 if none) |
| GET | /api/payments | list all payments |
| GET | /health | health check |

`method` is `CARD` or `CASH`. The amount is never sent by the client: it is read from Orders.

Response 201:

```json
{
  "id": "uuid",
  "orderId": "order-demo-001",
  "amount": 250.0,
  "method": "CARD",
  "status": "SUCCESS",
  "createdAt": "2026-11-07T14:00:00Z"
}
```

Errors are returned as `{ "message": "...", "detail": "..." }`:

| Code | Meaning |
|---|---|
| 404 | Order not found |
| 409 | Order is not awaiting payment / payment already done |
| 402 | Payment declined |
| 503 | Orders service or payment provider unavailable |
| 422 | Invalid request body |

Payment statuses: `SUCCESS`, `FAILED`, `REFUNDED`, `PENDING`.

## Dependency on Orders

Payments calls the Orders service (`ORDERS_URL`, default `http://localhost:8084`):

- `GET /api/orders/{id}`: reads `total` and `status` (must be `PENDING_PAYMENT`).
- `PATCH /api/orders/{id}/status` with `{ "status": "PAID" }` after a successful charge.

If the `PATCH` fails after a charge, the payment is refunded automatically (status `REFUNDED`) and the service answers 503.


## Test scenarios (simulated payment provider)

| `method` | Result |
|---|---|
| `CARD`, `CASH` | 201, `SUCCESS` |
| `TEST_DECLINE` | 402, order stays `PENDING_PAYMENT` |
| `TEST_TIMEOUT` | 503, provider unavailable |
| order total > 50000 | 402, limit exceeded |

After a failure, the same order can be paid again. After a `SUCCESS`, it cannot (409).

## Tests

```bash
python -m pytest -q
```

9 automated tests use a fake Orders client. `fake_orders.py` is a small stand-in for Orders (port 8084) for manual tests:

```bash
python -m uvicorn fake_orders:app --port 8084
```

## Configuration

| Variable | Default |
|---|---|
| `ORDERS_URL` | `http://localhost:8084` |
| `DATABASE_URL` | `sqlite:///./data/payments.db` |
