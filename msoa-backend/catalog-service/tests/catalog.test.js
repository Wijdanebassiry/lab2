const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const request = require('supertest');

// Copie temporaire de la base : les tests ne touchent pas à catalog.db
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'catalog-test-'));
const tmpDb = path.join(tmpDir, 'catalog.db');
fs.copyFileSync(path.join(__dirname, '..', 'catalog.db'), tmpDb);

process.env.DB_PATH = tmpDb;
process.env.HOST = '127.0.0.1';
process.env.PORT = '0';
process.env.FRONTEND_ORIGIN = 'http://localhost:5173';

const { app, db } = require('../server');

after(() => new Promise((resolve) => {
    db.close(() => {
        fs.rmSync(tmpDir, { recursive: true, force: true });
        resolve();
    });
}));

test('GET /products renvoie la liste des 6 produits', async () => {
    const res = await request(app).get('/products');
    assert.equal(res.status, 200);
    assert.ok(Array.isArray(res.body));
    assert.equal(res.body.length, 6);
});

test('chaque produit a les champs du contrat', async () => {
    const res = await request(app).get('/products');
    for (const p of res.body) {
        for (const key of ['id', 'name', 'category', 'price', 'image', 'description']) {
            assert.ok(key in p, `champ manquant : ${key}`);
        }
        assert.equal(typeof p.price, 'number');
    }
});

test('GET /products/:id renvoie le produit demandé', async () => {
    const res = await request(app).get('/products/1');
    assert.equal(res.status, 200);
    assert.equal(res.body.id, 1);
    assert.equal(res.body.name, 'ThinkPad Laptop');
});

test('GET /products/:id inconnu renvoie 404', async () => {
    const res = await request(app).get('/products/9999');
    assert.equal(res.status, 404);
    assert.equal(res.body.message, 'Product not found.');
});

test('GET /products/:id trop long renvoie 400', async () => {
    const res = await request(app).get(`/products/${'a'.repeat(101)}`);
    assert.equal(res.status, 400);
    assert.equal(res.body.message, 'Invalid product id.');
});

test('une injection SQL dans :id ne casse rien (404)', async () => {
    const res = await request(app).get('/products/' + encodeURIComponent("1 OR 1=1"));
    assert.equal(res.status, 404);
});

test('route inconnue renvoie 404 JSON', async () => {
    const res = await request(app).get('/nope');
    assert.equal(res.status, 404);
    assert.equal(res.body.message, 'Not found');
});

test('helmet ajoute ses en-têtes de sécurité', async () => {
    const res = await request(app).get('/products');
    assert.equal(res.headers['x-content-type-options'], 'nosniff');
});

test('CORS autorise l’origine du frontend uniquement', async () => {
    const ok = await request(app).get('/products').set('Origin', 'http://localhost:5173');
    assert.equal(ok.headers['access-control-allow-origin'], 'http://localhost:5173');
    const ko = await request(app).get('/products').set('Origin', 'http://evil.example');
    assert.equal(ko.headers['access-control-allow-origin'], undefined);
});
