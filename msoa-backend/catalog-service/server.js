const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const app = express();
app.use(express.json());

// Database connection & Auto-initialization
const dbPath = path.join(__dirname, 'catalog.db');
const db = new sqlite3.Database(dbPath, (err) => {
    if (err) {
        console.error('Error opening database', err.message);
    } else {
        console.log('Connected to the catalog SQLite database.');
        // Auto-create table and insert default products if not exists
        db.run(`CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            category TEXT
        )`, (createErr) => {
            if (!createErr) {
                db.get(`SELECT COUNT(*) as count FROM products`, (countErr, row) => {
                    if (!countErr && row.count === 0) {
                        const seedProducts = [
                            [1, 'Laptop HP EliteBook', 'Core i5 8th Gen, 16GB RAM, 512GB SSD', 8499, 10, 'Computers'],
                            [2, 'Smartphone Samsung Galaxy', '128GB, 8GB RAM, Black', 3499, 25, 'Phones'],
                            [3, 'Wireless Headphones', 'Noise cancelling, Bluetooth 5.0', 599, 50, 'Accessories'],
                            [4, 'Mechanical Keyboard', 'RGB backlit, Red switches', 799, 30, 'Accessories'],
                            [5, 'Gaming Mouse', 'Ergonomic, 16000 DPI', 399, 40, 'Accessories'],
                            [6, 'Monitor 24 inch', 'Full HD IPS, 75Hz', 1899, 15, 'Displays']
                        ];
                        const stmt = db.prepare(`INSERT OR IGNORE INTO products (id, name, description, price, stock, category) VALUES (?, ?, ?, ?, ?, ?)`);
                        seedProducts.forEach(prod => stmt.run(prod));
                        stmt.finalize();
                    }
                });
            }
        });
    }
});

// Conversion rates from environment variables or defaults
const RATE_EUR = parseFloat(process.env.RATE_EUR) || 10.87;
const RATE_USD = parseFloat(process.env.RATE_USD) || 10.0;

// ==========================================
// PARTIE I & II: API v1 (NE DOIT PAS CHANGER)
// ==========================================

// GET all products (v1)
app.get('/products', (req, res) => {
    const query = `SELECT id, name, description, price, stock, category FROM products`;
    db.all(query, [], (err, rows) => {
        if (err) {
            console.error("SQL Error DETAILS (v1 products):", err.message);
            return res.status(500).json({ error: err.message });
        }
        res.json(rows);
    });
});

// GET product by id (v1)
app.get('/products/:id', (req, res) => {
    const productId = req.params.id;
    const query = `SELECT id, name, description, price, stock, category FROM products WHERE id = ?`;
    db.get(query, [productId], (err, row) => {
        if (err) {
            console.error("SQL Error DETAILS (v1 product by id):", err.message);
            return res.status(500).json({ error: err.message });
        }
        if (!row) {
            return res.status(404).json({ error: 'Product not found' });
        }
        res.json(row);
    });
});


// ==========================================
// PARTIE III: API v2 (NEW - Structured Price)
// ==========================================

function convertPrice(priceInMAD, currency) {
    if (!currency || currency === 'MAD') {
        return { amount: priceInMAD, currency: 'MAD' };
    }
    if (currency === 'EUR') {
        const converted = Math.round((priceInMAD / RATE_EUR) * 100) / 100;
        return { amount: converted, currency: 'EUR' };
    }
    if (currency === 'USD') {
        const converted = Math.round((priceInMAD / RATE_USD) * 100) / 100;
        return { amount: converted, currency: 'USD' };
    }
    return null;
}

// GET all products (v2)
app.get('/v2/products', (req, res) => {
    const currency = req.query.currency || 'MAD';
    
    if (!['MAD', 'EUR', 'USD'].includes(currency)) {
        return res.status(400).json({ error: 'Invalid currency' });
    }

    const query = `SELECT id, name, description, price, stock, category FROM products`;
    db.all(query, [], (err, rows) => {
        if (err) {
            console.error("SQL Error DETAILS (v2 products):", err.message);
            return res.status(500).json({ error: err.message });
        }
        const updatedRows = rows.map(prod => {
            const formattedPrice = convertPrice(prod.price, currency);
            return {
                ...prod,
                price: formattedPrice
            };
        });
        res.json(updatedRows);
    });
});

// GET product by id (v2)
app.get('/v2/products/:id', (req, res) => {
    const productId = req.params.id;
    const currency = req.query.currency || 'MAD';

    if (!['MAD', 'EUR', 'USD'].includes(currency)) {
        return res.status(400).json({ error: 'Invalid currency' });
    }

    const query = `SELECT id, name, description, price, stock, category FROM products WHERE id = ?`;
    db.get(query, [productId], (err, row) => {
        if (err) {
            console.error("SQL Error DETAILS (v2 product by id):", err.message);
            return res.status(500).json({ error: err.message });
        }
        if (!row) {
            return res.status(404).json({ error: 'Product not found' });
        }

        const formattedPrice = convertPrice(row.price, currency);
        if (!formattedPrice) {
            return res.status(400).json({ error: 'Invalid currency' });
        }

        const updatedProduct = {
            ...row,
            price: formattedPrice
        };

        res.json(updatedProduct);
    });
});

const PORT = process.env.PORT || 8082;
app.listen(PORT, () => {
    console.log(`Catalog service running on port ${PORT}`);
});

module.exports = app;