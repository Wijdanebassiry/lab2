const path = require("path");
const { performance } = require("perf_hooks");
const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");

const countArg = Number(process.argv[2]);
const iterations = Number.isFinite(countArg) && countArg > 0 ? Math.floor(countArg) : 1000;

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

function startLocalBenchmarkServer() {
  return new Promise((resolve, reject) => {
    const server = new grpc.Server();
    server.addService(InventoryService.service, {
      CheckAvailability(call, callback) {
        callback(null, { available: true, items: call.request.items || [] });
      },
      Reserve(call, callback) {
        callback(null, {
          success: true,
          reservation_id: "bench-res",
          unavailable: [],
        });
      },
      Release(call, callback) {
        callback(null, {
          success: true,
          released: true,
        });
      },
    });
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

function percentile(sortedArr, p) {
  if (sortedArr.length === 0) return 0;
  const idx = Math.ceil((p / 100) * sortedArr.length) - 1;
  return sortedArr[Math.max(0, Math.min(sortedArr.length - 1, idx))];
}

async function runBenchmark() {
  const externalUrl = process.env.INVENTORY_GRPC_URL;
  let localServer = null;
  let targetUrl = externalUrl;

  if (!targetUrl) {
    const started = await startLocalBenchmarkServer();
    localServer = started.server;
    targetUrl = started.url;
  }

  process.env.INVENTORY_GRPC_URL = targetUrl;
  const { reserveStockGrpc } = require("../inventoryGrpc");

  const durations = [];
  const totalStart = performance.now();

  try {
    for (let i = 0; i < iterations; i += 1) {
      const t0 = performance.now();
      await reserveStockGrpc([{ product_id: "prod-1", quantity: 1 }]);
      durations.push(performance.now() - t0);
    }
  } finally {
    if (localServer) {
      localServer.forceShutdown();
    }
  }

  const totalMs = performance.now() - totalStart;
  durations.sort((a, b) => a - b);

  const avgMs = durations.reduce((acc, v) => acc + v, 0) / durations.length;
  const minMs = durations[0] || 0;
  const maxMs = durations[durations.length - 1] || 0;
  const p50Ms = percentile(durations, 50);
  const p95Ms = percentile(durations, 95);
  const p99Ms = percentile(durations, 99);
  const throughput = (iterations / (totalMs / 1000)).toFixed(2);

  console.log("=== gRPC Inventory Benchmark ===");
  console.log(`Target URL : ${targetUrl}`);
  console.log(`Iterations : ${iterations}`);
  console.log(`Total time : ${totalMs.toFixed(2)} ms`);
  console.log(`Throughput : ${throughput} req/s`);
  console.log(`Latency min: ${minMs.toFixed(3)} ms`);
  console.log(`Latency avg: ${avgMs.toFixed(3)} ms`);
  console.log(`Latency p50: ${p50Ms.toFixed(3)} ms`);
  console.log(`Latency p95: ${p95Ms.toFixed(3)} ms`);
  console.log(`Latency p99: ${p99Ms.toFixed(3)} ms`);
  console.log(`Latency max: ${maxMs.toFixed(3)} ms`);
}

runBenchmark().catch((err) => {
  console.error("Benchmark failed:", err);
  process.exit(1);
});