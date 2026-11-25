const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");

const PROTO_PATH = path.resolve(__dirname, "../../contracts/inventory.proto");
const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});
const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
const InventoryService = protoDescriptor.inventory.v1.Inventory;

function startMockGrpcServer(handlerOverrides = {}) {
  return new Promise((resolve, reject) => {
    const server = new grpc.Server();

    const handlers = {
      CheckAvailability(call, callback) {
        callback(null, { available: true, items: call.request.items || [] });
      },
      Reserve(call, callback) {
        const items = call.request.items || [];
        if (items.some((i) => !i.product_id || Number(i.quantity) <= 0)) {
          return callback({
            code: grpc.status.INVALID_ARGUMENT,
            message: "Invalid product_id or quantity",
          });
        }
        if (items.some((i) => Number(i.quantity) > 10)) {
          return callback(null, {
            success: false,
            unavailable: items
              .filter((i) => Number(i.quantity) > 10)
              .map((i) => ({
                product_id: i.product_id,
                requested: Number(i.quantity),
                available: 10,
              })),
          });
        }
        return callback(null, {
          success: true,
          reservation_id: "res-mock-1",
          unavailable: [],
        });
      },
      Release(call, callback) {
        return callback(null, {
          success: true,
          released: true,
        });
      },
      ...handlerOverrides,
    };

    server.addService(InventoryService.service, handlers);
    server.bindAsync(
      "127.0.0.1:0",
      grpc.ServerCredentials.createInsecure(),
      (err, port) => {
        if (err) return reject(err);
        resolve({ server, url: `127.0.0.1:${port}` });
      }
    );
  });
}

function loadFreshInventoryGrpc(url, deadlineMs = 1500) {
  process.env.INVENTORY_GRPC_URL = url;
  process.env.INVENTORY_GRPC_DEADLINE_MS = String(deadlineMs);
  delete require.cache[require.resolve("../inventoryGrpc")];
  return require("../inventoryGrpc");
}

test("reserveStockGrpc reserves valid items via gRPC", async () => {
  const { server, url } = await startMockGrpcServer();
  try {
    const { reserveStockGrpc } = loadFreshInventoryGrpc(url);
    const res = await reserveStockGrpc([{ product_id: "p1", quantity: 2 }]);
    assert.equal(res.success, true);
  } finally {
    server.forceShutdown();
  }
});

test("reserveStockGrpc maps insufficient stock to 409", async () => {
  const { server, url } = await startMockGrpcServer();
  try {
    const { reserveStockGrpc } = loadFreshInventoryGrpc(url);
    await assert.rejects(
      () => reserveStockGrpc([{ product_id: "p1", quantity: 99 }]),
      (err) => {
        assert.equal(err.statusCode, 409);
        assert.ok(Array.isArray(err.unavailable));
        assert.equal(err.unavailable.length, 1);
        return true;
      }
    );
  } finally {
    server.forceShutdown();
  }
});

test("reserveStockGrpc maps INVALID_ARGUMENT to 400", async () => {
  const { server, url } = await startMockGrpcServer();
  try {
    const { reserveStockGrpc } = loadFreshInventoryGrpc(url);
    await assert.rejects(
      () => reserveStockGrpc([{ product_id: "", quantity: -1 }]),
      (err) => {
        assert.equal(err.statusCode, 400);
        return true;
      }
    );
  } finally {
    server.forceShutdown();
  }
});

test("reserveStockGrpc maps unavailable gRPC server to 503", async () => {
  const { reserveStockGrpc } = loadFreshInventoryGrpc("127.0.0.1:59991", 500);
  await assert.rejects(
    () => reserveStockGrpc([{ product_id: "p1", quantity: 1 }]),
    (err) => {
      assert.equal(err.statusCode, 503);
      assert.equal(err.message, "Inventory service unavailable.");
      return true;
    }
  );
});

test("releaseStockGrpc releases stock via gRPC", async () => {
  const { server, url } = await startMockGrpcServer();
  try {
    const { releaseStockGrpc } = loadFreshInventoryGrpc(url);
    const res = await releaseStockGrpc([{ product_id: "p1", quantity: 2 }]);
    assert.equal(res.success, true);
  } finally {
    server.forceShutdown();
  }
});

test("releaseStockGrpc maps unavailable gRPC server to 503", async () => {
  const { releaseStockGrpc } = loadFreshInventoryGrpc("127.0.0.1:59992", 500);
  await assert.rejects(
    () => releaseStockGrpc([{ product_id: "p1", quantity: 2 }]),
    (err) => {
      assert.equal(err.statusCode, 503);
      assert.equal(err.message, "Inventory service unavailable.");
      return true;
    }
  );
});