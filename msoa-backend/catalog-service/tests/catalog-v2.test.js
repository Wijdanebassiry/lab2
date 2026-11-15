const { describe, test } = require('node:test');
const assert = require('node:assert');
const request = require('supertest');
const app = require('../server');

describe('Catalog Service API v2 Tests', () => {

    test('GET /v2/products returns products with structured price in MAD by default', async () => {
        const res = await request(app).get('/v2/products');
        assert.strictEqual(res.statusCode, 200);
        assert.ok(Array.isArray(res.body));
        assert.ok(res.body.length > 0);
        assert.ok('amount' in res.body[0].price);
        assert.strictEqual(res.body[0].price.currency, 'MAD');
    });

    test('GET /v2/products/1 returns product with structured price in MAD', async () => {
        const res = await request(app).get('/v2/products/1');
        assert.strictEqual(res.statusCode, 200);
        assert.strictEqual(res.body.id, 1);
        assert.deepStrictEqual(res.body.price, { amount: 8499, currency: 'MAD' });
    });

    test('GET /v2/products/1?currency=EUR converts price correctly to EUR', async () => {
        const res = await request(app).get('/v2/products/1?currency=EUR');
        assert.strictEqual(res.statusCode, 200);
        assert.strictEqual(res.body.price.currency, 'EUR');
        assert.strictEqual(res.body.price.amount, 781.88); // 8499 / 10.87 rounded
    });

    test('GET /v2/products/1?currency=USD converts price correctly to USD', async () => {
        const res = await request(app).get('/v2/products/1?currency=USD');
        assert.strictEqual(res.statusCode, 200);
        assert.strictEqual(res.body.price.currency, 'USD');
        assert.ok(res.body.price.amount > 0);
    });

    test('GET /v2/products?currency=JPY returns 400 error', async () => {
        const res = await request(app).get('/v2/products?currency=JPY');
        assert.strictEqual(res.statusCode, 400);
        assert.ok('error' in res.body);
    });

    test('GET /v2/products/1?currency=JPY returns 400 error', async () => {
        const res = await request(app).get('/v2/products/1?currency=JPY');
        assert.strictEqual(res.statusCode, 400);
        assert.ok('error' in res.body);
    });

    test('GET /products/1 (v1) still returns simple number price', async () => {
        const res = await request(app).get('/products/1');
        assert.strictEqual(res.statusCode, 200);
        assert.strictEqual(typeof res.body.price, 'number');
        assert.strictEqual(res.body.price, 8499);
    });

    test('GET /products (v1) still returns simple number prices', async () => {
        const res = await request(app).get('/products');
        assert.strictEqual(res.statusCode, 200);
        assert.strictEqual(typeof res.body[0].price, 'number');
    });

});