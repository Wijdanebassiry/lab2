const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const request = require('supertest');

// Base temporaire : le serveur la crée et la remplit au démarrage, catalog.db n'est jamais touchée
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'catalog-v2-test-'));
const tmpDb = path.join(tmpDir, 'catalog.db');

process.env.DB_PATH = tmpDb;
process.env.HOST = '127.0.0.1';
process.env.PORT = '0';
process.env.FRONTEND_ORIGIN = 'http://localhost:5173';
process.env.RATE_EUR = '10.87';
process.env.RATE_USD = '10';

const { app, db } = require('../server');

after(() => new Promise((resolve) => {
    db.close(() => {
        fs.rmSync(tmpDir, { recursive: true, force: true });
        resolve();
    });
}));

// ---------- v1 : le contrat ne doit PAS changer (consommateurs existants) ----------

test('v1 : /products garde price numérique et le champ image', async () => {
    const res = await request(app).get('/products');
    assert.equal(res.status, 200);
    for (const p of res.body) {
        assert.equal(typeof p.price, 'number');
        assert.ok('image' in p);
        assert.ok(!('stock' in p), 'le stock appartient à Inventory');
    }
});

test('v1 : /products/:id ignore ?currency et garde price numérique', async () => {
    const res = await request(app).get('/products/1?currency=EUR');
    assert.equal(res.status, 200);
    assert.equal(res.body.price, 8499);
});

test('v1 : annonce son successeur dans l’en-tête Link (corps inchangé)', async () => {
    const res = await request(app).get('/products/1');
    assert.match(res.headers.link, /\/v2\/products.*successor-version/);
});

// ---------- v2 : nouveau prix structuré ----------

test('v2 : /v2/products renvoie price = { amount, currency } en MAD par défaut', async () => {
    const res = await request(app).get('/v2/products');
    assert.equal(res.status, 200);
    assert.equal(res.body.length, 6);
    for (const p of res.body) {
        assert.equal(typeof p.price.amount, 'number');
        assert.equal(p.price.currency, 'MAD');
    }
});

test('v2 : /v2/products/1 en MAD', async () => {
    const res = await request(app).get('/v2/products/1');
    assert.equal(res.status, 200);
    assert.deepEqual(res.body.price, { amount: 8499, currency: 'MAD' });
});

test('v2 : même contenu que v1 hors prix', async () => {
    const v1 = (await request(app).get('/products/1')).body;
    const v2 = (await request(app).get('/v2/products/1')).body;
    const { price: _a, ...rest1 } = v1;
    const { price: _b, ...rest2 } = v2;
    assert.deepEqual(rest2, rest1);
});

test('v2 : ?currency=EUR convertit (8499 / 10.87)', async () => {
    const res = await request(app).get('/v2/products/1?currency=EUR');
    assert.deepEqual(res.body.price, { amount: 781.88, currency: 'EUR' });
});

test('v2 : ?currency=usd accepte la casse minuscule (8499 / 10)', async () => {
    const res = await request(app).get('/v2/products/1?currency=usd');
    assert.deepEqual(res.body.price, { amount: 849.9, currency: 'USD' });
});

test('v2 : devise non supportée -> 400 au format { message }', async () => {
    for (const url of ['/v2/products?currency=JPY', '/v2/products/1?currency=JPY']) {
        const res = await request(app).get(url);
        assert.equal(res.status, 400);
        assert.match(res.body.message, /Unsupported currency/);
    }
});

test('v2 : produit inconnu -> 404 au format { message }', async () => {
    const res = await request(app).get('/v2/products/9999');
    assert.equal(res.status, 404);
    assert.equal(res.body.message, 'Product not found.');
});