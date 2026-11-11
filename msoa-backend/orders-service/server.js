
const express = require("express");
const cors = require("cors");
const crypto = require("crypto");
const db = require("./database");

const app = express();
const PORT = process.env.PORT || 8084;

const AUTH_URL = process.env.AUTH_URL || "http://127.0.0.1:8081";
const CATALOG_URL = process.env.CATALOG_URL || "http://127.0.0.1:8082";
const INVENTORY_URL = process.env.INVENTORY_URL || "http://127.0.0.1:8083";
const SHIPPING_URL = process.env.SHIPPING_URL || "http://127.0.0.1:8086";

app.use(cors());
app.use(express.json());

// ---------- Authentication ----------

async function authenticate(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return res.status(401).json({
      message: "Authentication token is required.",
      error: "Authentication token is required."
    });
  }

  try {
    const response = await fetch(`${AUTH_URL}/api/auth/me`, {
      method: "GET",
      headers: {
        Authorization: authHeader
      }
    });

    const user = await response.json();

    if (!response.ok || !user.id) {
      return res.status(401).json({
        message: user.message || "Invalid or expired token.",
        error: user.error || "Invalid or expired token."
      });
    }

    req.user = user;
    next();

  } catch (error) {
    console.error("Auth service error:", error.message);

    return res.status(503).json({
      message: "Authentication service unavailable.",
      error: "Authentication service unavailable."
    });
  }
}

// ---------- Helpers ----------

async function apiCall(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();

  let data = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    const error = new Error(
      data?.detail ||
      data?.message ||
      `External service error: ${response.status}`
    );

    error.status = response.status;
    throw error;
  }

  return data;
}

function mapOrder(order) {
  const items = db.prepare(`
    SELECT
      product_id AS productId,
      name,
      price,
      quantity
    FROM order_items
    WHERE order_id = ?
  `).all(order.id);

  return {
    id: order.id,
    userId: order.user_id,
    customer: {
      name: order.customer_name,
      address: order.customer_address,
      city: order.customer_city
    },
    total: order.total,
    status: order.status,
    createdAt: order.created_at,
    items
  };
}

function getOrderItems(orderId) {
  return db.prepare(`
    SELECT
      product_id AS productId,
      quantity
    FROM order_items
    WHERE order_id = ?
  `).all(orderId);
}

async function reserveStock(items) {
  return apiCall(`${INVENTORY_URL}/api/inventory/reserve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      items: items.map(item => ({
        productId: String(item.productId),
        quantity: item.quantity
      }))
    })
  });
}

async function releaseStock(items) {
  return apiCall(`${INVENTORY_URL}/api/inventory/release`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      items: items.map(item => ({
        productId: String(item.productId),
        quantity: item.quantity
      }))
    })
  });
}

// ---------- Health check ----------

app.get("/", (req, res) => {
  res.json({
    message: "Orders Microservice is running!"
  });
});

// ---------- GET all orders ----------

app.get("/api/orders", authenticate, (req, res) => {
  try {
    let orders;

    if (req.user.role === "ADMIN") {
      orders = db.prepare(`
        SELECT *
        FROM orders
        ORDER BY created_at DESC
      `).all();
    } else {
      orders = db.prepare(`
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC
      `).all(req.user.id);
    }

    res.json(orders.map(mapOrder));

  } catch (error) {
    console.error("Error fetching orders:", error);

    res.status(500).json({
      message: "Failed to fetch orders."
    });
  }
});

// ---------- GET order by ID ----------

app.get("/api/orders/:id", authenticate, (req, res) => {
  try {
    const order = db.prepare(`
      SELECT *
      FROM orders
      WHERE id = ?
    `).get(req.params.id);

    if (!order) {
      return res.status(404).json({
        message: "Order not found."
      });
    }

    if (
      req.user.role !== "ADMIN" &&
      String(order.user_id) !== String(req.user.id)
    ) {
      return res.status(403).json({
        message: "You are not allowed to access this order."
      });
    }

    res.json(mapOrder(order));

  } catch (error) {
    console.error("Error fetching order:", error);

    res.status(500).json({
      message: "Failed to fetch order."
    });
  }
});

// ---------- POST create order ----------

app.post("/api/orders", authenticate, async (req, res) => {
  let stockReserved = false;
  let normalizedItems = [];

  try {
    const { customer, items } = req.body;
    const userId = req.user.id;

    if (
      !customer?.name ||
      !customer?.address ||
      !customer?.city
    ) {
      return res.status(400).json({
        message: "Customer name, address and city are required."
      });
    }

    if (!Array.isArray(items) || items.length === 0) {
      return res.status(400).json({
        message: "Order must contain at least one item."
      });
    }

    // Validate and combine duplicate product IDs.
    const quantities = new Map();

    for (const item of items) {
      const productId = Number(item.productId);
      const quantity = Number(item.quantity);

      if (
        !Number.isInteger(productId) ||
        productId <= 0 ||
        !Number.isInteger(quantity) ||
        quantity <= 0
      ) {
        return res.status(400).json({
          message: "Invalid productId or quantity."
        });
      }

      quantities.set(
        productId,
        (quantities.get(productId) || 0) + quantity
      );
    }

    // Get authoritative product information from Catalog.
    for (const [productId, quantity] of quantities) {
      const product = await apiCall(
        `${CATALOG_URL}/products/${productId}`
      );

      if (
        !product ||
        product.id == null ||
        !Number.isFinite(Number(product.price)) ||
        Number(product.price) < 0
      ) {
        return res.status(502).json({
          message: `Invalid product information for product ${productId}.`
        });
      }

      normalizedItems.push({
        productId,
        name: product.name,
        price: Number(product.price),
        quantity
      });
    }

    const total = normalizedItems.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0
    );

    // Reserve stock before saving the order.
    await reserveStock(normalizedItems);
    stockReserved = true;

    const orderId = crypto.randomUUID();
    const createdAt = new Date().toISOString();

    // Save order and items in one SQLite transaction.
    const saveOrder = db.transaction(() => {
      db.prepare(`
        INSERT INTO orders (
          id,
          user_id,
          customer_name,
          customer_address,
          customer_city,
          total,
          status,
          created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        orderId,
        userId,
        customer.name,
        customer.address,
        customer.city,
        total,
        "PENDING_PAYMENT",
        createdAt
      );

      const insertItem = db.prepare(`
        INSERT INTO order_items (
          order_id,
          product_id,
          name,
          price,
          quantity
        )
        VALUES (?, ?, ?, ?, ?)
      `);

      for (const item of normalizedItems) {
        insertItem.run(
          orderId,
          item.productId,
          item.name,
          item.price,
          item.quantity
        );
      }
    });

    saveOrder();
    stockReserved = false;

    const savedOrder = db.prepare(`
      SELECT *
      FROM orders
      WHERE id = ?
    `).get(orderId);

    return res.status(201).json(mapOrder(savedOrder));

  } catch (error) {
    console.error("Error creating order:", error);

    // Release stock if saving the order failed.
    if (stockReserved) {
      try {
        await releaseStock(normalizedItems);
      } catch (releaseError) {
        console.error(
          "CRITICAL: Could not release reserved stock:",
          releaseError
        );
      }
    }

    res.status(error.status || 500).json({
      message: error.message || "Failed to create order."
    });
  }
});

// ---------- PATCH order status ----------

app.patch("/api/orders/:id/status", authenticate, (req, res) => {
  try {
    const { status } = req.body;
    const orderId = req.params.id;

    const order = db.prepare(`
      SELECT *
      FROM orders
      WHERE id = ?
    `).get(orderId);

    if (!order) {
      return res.status(404).json({
        message: "Order not found."
      });
    }

    if (String(order.user_id) !== String(req.user.id)) {
      return res.status(403).json({
        message: "You are not allowed to update this order."
      });
    }

    const transitions = {
      PENDING_PAYMENT: ["PAID"],
      PAID: ["SHIPPED"],
      SHIPPED: ["DELIVERED"],
      DELIVERED: [],
      CANCELLED: []
    };

    if (!transitions[order.status]?.includes(status)) {
      return res.status(400).json({
        message: `Invalid status transition: ${order.status} -> ${status}`
      });
    }

    db.prepare(`
      UPDATE orders
      SET status = ?
      WHERE id = ?
    `).run(status, orderId);

    const updatedOrder = db.prepare(`
      SELECT *
      FROM orders
      WHERE id = ?
    `).get(orderId);

    res.json(mapOrder(updatedOrder));

  } catch (error) {
    console.error("Error updating order status:", error);

    res.status(500).json({
      message: "Failed to update order status."
    });
  }
});

// ---------- POST cancel order ----------

app.post("/api/orders/:id/cancel", authenticate, async (req, res) => {
  let stockReleased = false;
  let items = [];
  let originalStatus = null;

  try {
    const orderId = req.params.id;

    const order = db.prepare(`
      SELECT *
      FROM orders
      WHERE id = ?
    `).get(orderId);

    if (!order) {
      return res.status(404).json({
        message: "Order not found."
      });
    }

    if (String(order.user_id) !== String(req.user.id)) {
      return res.status(403).json({
        message: "You are not allowed to cancel this order."
      });
    }

    if (!["PENDING_PAYMENT", "PAID"].includes(order.status)) {
      return res.status(400).json({
        message: "This order cannot be cancelled."
      });
    }

    // Check whether the order has already been shipped.
    let shipment = null;

    try {
      shipment = await apiCall(
        `${SHIPPING_URL}/api/shipments/order/${encodeURIComponent(orderId)}`,
        {
          method: "GET",
          headers: {
            Authorization: req.headers.authorization
          }
        }
      );
    } catch (error) {
      if (error.status !== 404) {
        throw error;
      }
    }

    if (
      shipment &&
      !["PREPARING", "CANCELLED"].includes(shipment.status)
    ) {
      return res.status(409).json({
        message: "Cannot cancel an order that has already been shipped."
      });
    }

    items = getOrderItems(orderId);
    originalStatus = order.status;

    // Release reserved stock.
    await releaseStock(items);
    stockReleased = true;

    // Update status only if it is still cancellable.
    const result = db.prepare(`
      UPDATE orders
      SET status = 'CANCELLED'
      WHERE id = ? AND status = ?
    `).run(orderId, originalStatus);

    if (result.changes !== 1) {
      throw new Error(
        "Order status changed; cancellation was not completed."
      );
    }

    const cancelledOrder = db.prepare(`
      SELECT *
      FROM orders
      WHERE id = ?
    `).get(orderId);

    stockReleased = false;

    res.json(mapOrder(cancelledOrder));

  } catch (error) {
    console.error("Error cancelling order:", error);

    // Restore stock if cancellation failed after releasing it.
    if (stockReleased) {
      try {
        await reserveStock(items);
      } catch (reserveError) {
        console.error(
          "CRITICAL: Could not restore stock after failed cancellation:",
          reserveError
        );
      }
    }

    res.status(error.status || 500).json({
      message: error.message || "Failed to cancel order."
    });
  }
});

// ---------- Start server ----------

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Orders Service running on port ${PORT}`);
  });
}

module.exports = app;
