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
const dbPath = process.env.DB_PATH || path.resolve(__dirname, 'catalog.db');
const db = new sqlite3.Database(dbPath, (err) => {
    if (err) console.error(`[Catalog] Database error: ${err.message}`);
    else {
        console.log('[Catalog] Connected to catalog.db');
        db.exec("PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;");
    }
});

const all = (sql, params = []) => new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => { if (err) reject(err); else resolve(rows); });
});
const get = (sql, params = []) => new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => { if (err) reject(err); else resolve(row); });
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
