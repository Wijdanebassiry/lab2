
const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Database = require("better-sqlite3");

let mockServer;
let appServer;
let db;
let baseUrl;
let tempDir;

let inventoryStatus = 200;
const shipmentStatuses = new Map();

const validOrder = {
  customer: {
    name: "Test Customer",
    address: "Test Address",
    city: "Casablanca"
  },
  items: [{ productId: 1, quantity: 2 }]
};

function insertOrder(id, status = "PENDING_PAYMENT") {
  db.prepare(`
    INSERT INTO orders (
      id, user_id, customer_name, customer_address,
      customer_city, total, status, created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    id, "user-1", "Test Customer", "Test Address",
    "Casablanca", 100, status, new Date().toISOString()
  );

  db.prepare(`
    INSERT INTO order_items (
      order_id, product_id, name, price, quantity
    )
    VALUES (?, ?, ?, ?, ?)
  `).run(id, 1, "Test Product", 50, 2);
}

// Send requests with CUSTOMER or ADMIN token
async function send(method, route, body, token = "valid-token") {
  return fetch(`${baseUrl}${route}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    ...(body ? { body: JSON.stringify(body) } : {})
  });
}

test.before(async () => {
  // Create an isolated temporary database.
  tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "orders-test-"));
  const dbPath = path.join(tempDir, "orders-test.db");

  const schemaPath = path.join(
    __dirname,
    "..",
    "..",
    "msoa_sqlite_databases",
    "orders",
    "schema.sql"
  );

  db = new Database(dbPath);
  db.exec(fs.readFileSync(schemaPath, "utf8"));
  db.close();

  process.env.ORDERS_DB_PATH = dbPath;

  // Mock external services.
  mockServer = http.createServer((req, res) => {
    res.setHeader("Content-Type", "application/json");

    // Auth service
    if (req.url === "/api/auth/me") {
      if (req.headers.authorization === "Bearer valid-token") {
        return res.end(JSON.stringify({
          id: "user-1",
          role: "CUSTOMER"
        }));
      }

      if (req.headers.authorization === "Bearer admin-token") {
        return res.end(JSON.stringify({
          id: "admin-1",
          role: "ADMIN"
        }));
      }

      res.statusCode = 401;
      return res.end(JSON.stringify({
        message: "Invalid token"
      }));
    }

    // Catalog service
    if (req.method === "GET" && req.url === "/products/1") {
      return res.end(JSON.stringify({
        id: 1,
        name: "Test Product",
        price: 50
      }));
    }

    // Inventory service
    if (req.url === "/api/inventory/reserve") {
      res.statusCode = inventoryStatus;
      return res.end(JSON.stringify(
        inventoryStatus === 409
          ? { message: "Insufficient stock." }
          : { message: "Stock reserved." }
      ));
    }

    if (req.url === "/api/inventory/release") {
      return res.end(JSON.stringify({
        message: "Stock released."
      }));
    }

    // Shipping service
    if (
      req.method === "GET" &&
      req.url.startsWith("/api/shipments/order/")
    ) {
      const orderId = decodeURIComponent(
        req.url.split("/").pop()
      );

      // Verify that Orders forwards the authorization token.
      if (req.headers.authorization !== "Bearer valid-token") {
        res.statusCode = 401;
        return res.end(JSON.stringify({
          message: "Missing authorization token."
        }));
      }

      const status = shipmentStatuses.get(orderId);

      if (!status) {
        res.statusCode = 404;
        return res.end(JSON.stringify({
          message: "Shipment not found."
        }));
      }

      return res.end(JSON.stringify({ status }));
    }

    res.statusCode = 404;
    res.end(JSON.stringify({
      message: "Mock route not found."
    }));
  });

  await new Promise(resolve =>
    mockServer.listen(0, "127.0.0.1", resolve)
  );

  const mockUrl = `http://127.0.0.1:${mockServer.address().port}`;

  process.env.AUTH_URL = mockUrl;
  process.env.CATALOG_URL = mockUrl;
  process.env.INVENTORY_URL = mockUrl;
  process.env.SHIPPING_URL = mockUrl;

  // Load Orders after setting environment variables.
  const app = require("../server");
  db = require("../database");

  // Existing test data
  insertOrder("order-1");

  insertOrder("order-2");
  db.prepare(`
    UPDATE orders SET user_id = ? WHERE id = ?
  `).run("user-2", "order-2");

  appServer = http.createServer(app);

  await new Promise(resolve =>
    appServer.listen(0, "127.0.0.1", resolve)
  );

  baseUrl = `http://127.0.0.1:${appServer.address().port}`;
});

test.after(async () => {
  if (appServer) {
    await new Promise(resolve => appServer.close(resolve));
  }

  if (db && db.open) {
    db.close();
  }

  if (mockServer) {
    await new Promise(resolve => mockServer.close(resolve));
  }

  if (tempDir) {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }

  delete process.env.ORDERS_DB_PATH;
  delete process.env.AUTH_URL;
  delete process.env.CATALOG_URL;
  delete process.env.INVENTORY_URL;
  delete process.env.SHIPPING_URL;
});

// ------------------------------------
// GET tests (3)
// ------------------------------------

test("GET /api/orders rejects requests without a token", async () => {
  const response = await fetch(`${baseUrl}/api/orders`);

  assert.equal(response.status, 401);
});

test("GET /api/orders rejects invalid tokens", async () => {
  const response = await fetch(`${baseUrl}/api/orders`, {
    headers: {
      Authorization: "Bearer invalid-token"
    }
  });

  assert.equal(response.status, 401);
});

test("GET /api/orders returns only the authenticated user's orders", async () => {
  const response = await send("GET", "/api/orders");

  assert.equal(response.status, 200);

  const orders = await response.json();

  assert.equal(orders.length, 1);
  assert.equal(orders[0].id, "order-1");
  assert.equal(orders[0].userId, "user-1");
});

// ------------------------------------
// ADMIN authorization tests (3)
// ------------------------------------

test("ADMIN can see all users' orders", async () => {
  const response = await send(
    "GET",
    "/api/orders",
    undefined,
    "admin-token"
  );

  assert.equal(response.status, 200);

  const orders = await response.json();
  const orderIds = orders.map(order => order.id);

  assert.ok(orderIds.includes("order-1"));
  assert.ok(orderIds.includes("order-2"));
});

test("ADMIN can access another user's order details", async () => {
  const response = await send(
    "GET",
    "/api/orders/order-2",
    undefined,
    "admin-token"
  );

  assert.equal(response.status, 200);

  const order = await response.json();

  assert.equal(order.id, "order-2");
  assert.equal(order.userId, "user-2");
});

test("CUSTOMER cannot access another user's order details", async () => {
  const response = await send(
    "GET",
    "/api/orders/order-2"
  );

  assert.equal(response.status, 403);
});

// ------------------------------------
// POST tests (3)
// ------------------------------------

test("POST /api/orders creates an order successfully", async () => {
  inventoryStatus = 200;

  const response = await send(
    "POST",
    "/api/orders",
    validOrder
  );

  assert.equal(response.status, 201);

  const order = await response.json();

  assert.equal(order.status, "PENDING_PAYMENT");
  assert.equal(order.total, 100);
  assert.equal(order.items.length, 1);
  assert.equal(order.items[0].quantity, 2);
});

test("POST /api/orders rejects an invalid body", async () => {
  const response = await send(
    "POST",
    "/api/orders",
    {
      customer: {},
      items: []
    }
  );

  assert.equal(response.status, 400);
});

test("POST /api/orders returns 409 when stock is insufficient", async () => {
  inventoryStatus = 409;

  const response = await send(
    "POST",
    "/api/orders",
    validOrder
  );

  assert.equal(response.status, 409);

  inventoryStatus = 200;
});

// ------------------------------------
// PATCH tests (2)
// ------------------------------------

test("PATCH /api/orders/:id/status accepts a valid transition", async () => {
  const response = await send(
    "PATCH",
    "/api/orders/order-1/status",
    { status: "PAID" }
  );

  assert.equal(response.status, 200);

  const order = await response.json();

  assert.equal(order.status, "PAID");
});

test("PATCH /api/orders/:id/status rejects an invalid transition", async () => {
  insertOrder("patch-invalid");

  const response = await send(
    "PATCH",
    "/api/orders/patch-invalid/status",
    { status: "DELIVERED" }
  );

  assert.equal(response.status, 400);
});

// ------------------------------------
// Cancellation tests (3)
// ------------------------------------

test("Cancel order in PENDING_PAYMENT status", async () => {
  insertOrder("cancel-pending");

  const response = await send(
    "POST",
    "/api/orders/cancel-pending/cancel"
  );

  assert.equal(response.status, 200);

  const order = await response.json();

  assert.equal(order.status, "CANCELLED");
});

test("Cancel order in PAID status", async () => {
  insertOrder("cancel-paid", "PAID");

  const response = await send(
    "POST",
    "/api/orders/cancel-paid/cancel"
  );

  assert.equal(response.status, 200);

  const order = await response.json();

  assert.equal(order.status, "CANCELLED");
});

test("Cancel order returns 409 when shipment is already shipped", async () => {
  insertOrder("cancel-shipped", "PAID");

  shipmentStatuses.set("cancel-shipped", "SHIPPED");

  const response = await send(
    "POST",
    "/api/orders/cancel-shipped/cancel"
  );

  assert.equal(response.status, 409);

  const order = db.prepare(`
    SELECT status FROM orders WHERE id = ?
  `).get("cancel-shipped");

  assert.equal(order.status, "PAID");
});
