const path = require("path");
const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");

const PROTO_PATH = path.resolve(__dirname, "../contracts/inventory.proto");
const DEFAULT_GRPC_URL = "127.0.0.1:50051";
const DEFAULT_DEADLINE_MS = 2000;

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
const InventoryService = protoDescriptor.inventory.v1.Inventory;

let cachedClient = null;
let cachedTarget = null;

function getGrpcUrl() {
  return process.env.INVENTORY_GRPC_URL || DEFAULT_GRPC_URL;
}

function getDeadlineMs() {
  const parsed = Number(process.env.INVENTORY_GRPC_DEADLINE_MS);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_DEADLINE_MS;
}

function getClient() {
  const target = getGrpcUrl();
  if (!cachedClient || cachedTarget !== target) {
    cachedClient = new InventoryService(
      target,
      grpc.credentials.createInsecure()
    );
    cachedTarget = target;
  }
  return cachedClient;
}

function createHttpError(message, statusCode, extra = {}) {
  const err = new Error(message);
  err.statusCode = statusCode;
  Object.assign(err, extra);
  return err;
}

function mapGrpcError(grpcErr) {
  if (!grpcErr) {
    return createHttpError("Inventory service unavailable.", 503);
  }
  if (grpcErr.code === grpc.status.INVALID_ARGUMENT) {
    return createHttpError(
      grpcErr.details || grpcErr.message || "Invalid inventory request.",
      400
    );
  }
  if (
    grpcErr.code === grpc.status.UNAVAILABLE ||
    grpcErr.code === grpc.status.DEADLINE_EXCEEDED
  ) {
    return createHttpError("Inventory service unavailable.", 503);
  }
  return createHttpError(
    grpcErr.details || grpcErr.message || "Inventory service unavailable.",
    503
  );
}

function normalizeItems(items) {
  if (!Array.isArray(items)) {
    return [];
  }
  return items.map((item) => ({
    product_id: String(item.product_id),
    quantity: Number(item.quantity),
  }));
}

function reserveStockGrpc(items) {
  const client = getClient();
  const payload = { items: normalizeItems(items) };
  const deadline = new Date(Date.now() + getDeadlineMs());

  return new Promise((resolve, reject) => {
    client.Reserve(payload, { deadline }, (err, response) => {
      if (err) {
        return reject(mapGrpcError(err));
      }
      if (!response || response.success !== true) {
        const unavailable =
          response && Array.isArray(response.unavailable)
            ? response.unavailable
            : [];
        return reject(
          createHttpError("Insufficient stock for reservation.", 409, {
            unavailable,
          })
        );
      }
      return resolve(response);
    });
  });
}

function releaseStockGrpc(items) {
  const client = getClient();
  const payload = { items: normalizeItems(items) };
  const deadline = new Date(Date.now() + getDeadlineMs());

  return new Promise((resolve, reject) => {
    client.Release(payload, { deadline }, (err, response) => {
      if (err) {
        return reject(mapGrpcError(err));
      }
      return resolve(response);
    });
  });
}

module.exports = {
  reserveStockGrpc,
  releaseStockGrpc,
  getGrpcUrl,
  getDeadlineMs,
};