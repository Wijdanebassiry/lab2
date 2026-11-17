try { require('dotenv').config(); } catch (_) { }
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

// Config
const PORT = Number(process.env.PORT);
const HOST = process.env.HOST;
const ALLOWED_ORIGINS = process.env.FRONTEND_ORIGIN.split(',').map(s => s.trim()).filter(Boolean);

class HttpError extends Error {
    constructor(status, message) { super(message); this.status = status; }
}
const wrap = fn => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);

// App
const app = express();
app.use(helmet());
app.use(cors({ origin: ALLOWED_ORIGINS, methods: ['GET'], allowedHeaders: ['Content-Type', 'Authorization'] }));
app.use(express.json({ limit: '10kb' }));

// Database
// catalog.db is not versioned (*.db is git-ignored): the table is created and seeded on first start.
const SEED_PRODUCTS = [
    [1, 'ThinkPad Laptop', 'Electronics', 8499.0, '', 'Business laptop'],
    [2, 'Wireless Mouse', 'Accessories', 199.0, '', 'Wireless optical mouse'],
    [3, 'Mechanical Keyboard', 'Accessories', 599.0, '', 'Mechanical keyboard'],
    [4, 'USB-C Hub', 'Accessories', 349.0, '', 'Multiport USB-C adapter'],
    [5, '27-inch Monitor', 'Electronics', 2299.0, '', 'Full HD display'],
    [6, 'Laptop Backpack', 'Accessories', 399.0, '', 'Protective laptop backpack']
];

let markReady;
const ready = new Promise((resolve) => { markReady = resolve; });

const dbPath = process.env.DB_PATH || path.resolve(__dirname, 'catalog.db');
const db = new sqlite3.Database(dbPath, async (err) => {
    if (err) {
        console.error(`[Catalog] Database error: ${err.message}`);
    } else {
        console.log('[Catalog] Connected to catalog.db');
        db.exec("PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;");
        try { await initDatabase(); } catch (e) { console.error(`[Catalog] Init error: ${e.message}`); }
    }
    markReady();
});

const run = (sql, params = []) => new Promise((resolve, reject) => {
    db.run(sql, params, (err) => { if (err) reject(err); else resolve(); });
});

async function initDatabase() {
    await run(`CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL CHECK(price >= 0),
        image TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT ''
    )`);
    const row = await new Promise((resolve, reject) => {
        db.get("SELECT COUNT(*) AS n FROM products", (err, r) => { if (err) reject(err); else resolve(r); });
    });
    if (row.n === 0) {
        for (const p of SEED_PRODUCTS) {
            await run("INSERT INTO products (id, name, category, price, image, description) VALUES (?, ?, ?, ?, ?, ?)", p);
        }
    }
}

const all = async (sql, params = []) => {
    await ready;
    return new Promise((resolve, reject) => {
        db.all(sql, params, (err, rows) => { if (err) reject(err); else resolve(rows); });
    });
};
const get = async (sql, params = []) => {
    await ready;
    return new Promise((resolve, reject) => {
        db.get(sql, params, (err, row) => { if (err) reject(err); else resolve(row); });
    });
};

// ---------------------------------------------------------------------------
// API versions
//   v1  /products, /products/:id        price = NUMBER in MAD. FROZEN: its shape never changes.
//   v2  /v2/products, /v2/products/:id  price = { amount, currency }, optional ?currency=
// Rates = how many MAD one unit of the currency is worth (1 EUR = 10.87 MAD). Override with RATE_EUR / RATE_USD.
// ---------------------------------------------------------------------------
const MAD_PER_UNIT = {
    MAD: 1,
    EUR: Number(process.env.RATE_EUR) || 10.87,
    USD: Number(process.env.RATE_USD) || 10.0,
};

function readCurrency(req) {
    const currency = String(req.query.currency || 'MAD').toUpperCase();
    if (!Object.hasOwn(MAD_PER_UNIT, currency)) {
        throw new HttpError(400, `Unsupported currency. Supported: ${Object.keys(MAD_PER_UNIT).join(', ')}.`);
    }
    return currency;
}

// v1 row -> v2 representation (only the price changes)
function toV2(product, currency) {
    const amount = Math.round((product.price / MAD_PER_UNIT[currency]) * 100) / 100;
    return { ...product, price: { amount, currency } };
}

// Tell v1 consumers where the successor lives (adds a header, changes no body)
app.use('/products', (req, res, next) => {
    res.set('Link', '</v2/products>; rel="successor-version"');
    next();
});

// 1. GET ALL PRODUCTS
app.get('/products', wrap(async (req, res) => {
    res.json(await all("SELECT * FROM products"));
}));

// 2. GET PRODUCT BY ID
app.get('/products/:id', wrap(async (req, res) => {
    const id = req.params.id;
    if (!id || id.length > 100) throw new HttpError(400, 'Invalid product id.');
    const product = await get("SELECT * FROM products WHERE id = ?", [id]);
    if (!product) throw new HttpError(404, 'Product not found.');
    res.json(product);
}));

// 3. V2 - GET ALL PRODUCTS (price = { amount, currency })
app.get('/v2/products', wrap(async (req, res) => {
    const currency = readCurrency(req);
    const rows = await all("SELECT * FROM products");
    res.json(rows.map(p => toV2(p, currency)));
}));

// 4. V2 - GET PRODUCT BY ID
app.get('/v2/products/:id', wrap(async (req, res) => {
    const currency = readCurrency(req);
    const id = req.params.id;
    if (!id || id.length > 100) throw new HttpError(400, 'Invalid product id.');
    const product = await get("SELECT * FROM products WHERE id = ?", [id]);
    if (!product) throw new HttpError(404, 'Product not found.');
    res.json(toV2(product, currency));
}));

// Error handling
app.use((req, res) => res.status(404).json({ message: 'Not found' }));
app.use((err, req, res, next) => {
    if (err instanceof HttpError) return res.status(err.status).json({ message: err.message });
    if (err.type === 'entity.parse.failed') return res.status(400).json({ message: 'Malformed JSON body.' });
    console.error('[Catalog] Unhandled error:', err);
    res.status(500).json({ message: 'Internal server error' });
});

if (require.main === module) {
    app.listen(PORT, HOST, () => console.log(`[Catalog] Independent Service listening on ${HOST}:${PORT}`));
}

module.exports = { app, db };