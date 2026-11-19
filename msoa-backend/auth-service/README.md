# Auth Service

Authentication microservice of the MSOA e-commerce platform (Lab 2).
Owner: Hiba. Stack: Python, Django, Django REST Framework, SimpleJWT, SQLite.

## Responsibility

The Auth service answers one question for the whole platform: who is this user?
It owns the `users` data (id, name, email, hashed password, role). Other services
store only a `userId` and never access this database.

## Requirements

- Python 3.10+
- pip

## Installation

From the `auth-service` folder:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
```

On Linux or macOS, activate the environment with `source venv/bin/activate`.

## Run

```powershell
python manage.py runserver 8081
```

The service listens on `http://localhost:8081`.
CORS is enabled for the frontend (`http://localhost:5173`).

## Demo account

| Email | Password | Id | Role |
|---|---|---|---|
| `demo@msoa.shop` | `demo123` | `user-1` | `CUSTOMER` |

Created by `python manage.py seed_demo`. The password is stored hashed.

## Endpoints

Protected endpoints expect the header `Authorization: Bearer <token>`.

### POST `/api/auth/login`

Request:

```json
{ "email": "demo@msoa.shop", "password": "demo123" }
```

Response `200`:

```json
{
  "user": {
    "id": "user-1",
    "name": "Demo Customer",
    "email": "demo@msoa.shop",
    "role": "CUSTOMER"
  },
  "token": "<jwt>"
}
```

Error `401`: `Invalid email or password.`

### POST `/api/auth/register`

Request:

```json
{ "name": "Test User", "email": "test@msoa.shop", "password": "test123" }
```

Response `201`: the `user` object (without token).

Errors: `400` `All fields are required.`, `409` `Email already registered.`

### POST `/api/auth/logout`

Requires the token. Response `204` with no body.
The token is stateless: the frontend deletes its session, and the token expires after 1 day.

### GET `/api/auth/me`

Requires the token. Response `200`: the `user` object.
Error `401` if the token is missing or invalid.
Other services can use this endpoint to verify a token.

## Error format

Every error returns both keys, so the frontend (which reads `message`) and the team
contract (which uses `error`) are both satisfied:

```json
{ "message": "Invalid email or password.", "error": "Invalid email or password." }
```

## Automated tests

```powershell
python manage.py test
```

15 tests cover the 4 endpoints, using a temporary test database (the real
`db.sqlite3` and the demo account are not touched):

- login: success (`user` + `token`, no password), email case/spaces ignored, wrong password (401), unknown email (401), error body has `message` and `error`;
- register: 201 without token, password stored hashed, missing field (400), duplicate email (409), new account can log in;
- me: valid token (200), no token (401), invalid token (401);
- logout: valid token (204), no token (401).

## Quick test (PowerShell)

```powershell
$body = '{"email":"demo@msoa.shop","password":"demo123"}'
$session = Invoke-RestMethod -Method Post -Uri http://localhost:8081/api/auth/login -ContentType "application/json" -Body $body
$h = @{ Authorization = "Bearer $($session.token)" }
Invoke-RestMethod -Uri http://localhost:8081/api/auth/me -Headers $h
```

## Connect to the frontend

In the provided React project, open `src/config/backend.js`, set `AUTH: "rest"`
in `BACKEND_MODE` and keep `API_URLS.AUTH` at `http://localhost:8081`.

## Project structure

```
auth-service/
├── config/                 Django settings and root URLs
├── accounts/
│   ├── models.py           Custom User model (email login, text id, role)
│   ├── views.py            login, register, logout, me
│   ├── urls.py             routes (no trailing slash)
│   ├── exceptions.py       error format with "message" and "error"
│   └── management/commands/seed_demo.py
├── manage.py
└── requirements.txt
```
