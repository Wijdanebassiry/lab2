const Database = require("better-sqlite3");
const fs = require("fs");
const path = require("path");

const dbDir = path.join(__dirname, "..", "msoa_sqlite_databases", "orders");
const dbPath = path.join(dbDir, "orders.db");

fs.mkdirSync(dbDir, { recursive: true });

if (fs.existsSync(dbPath)) {
  console.log("Orders database already exists. Initialization skipped.");
  process.exit(0);
}

const db = new Database(dbPath);

try {
  db.exec(fs.readFileSync(path.join(dbDir, "schema.sql"), "utf8"));
  db.exec(fs.readFileSync(path.join(dbDir, "seed.sql"), "utf8"));
  console.log("Orders database initialized successfully!");
} catch (error) {
  console.error("Database initialization failed:", error.message);
  process.exitCode = 1;
} finally {
  db.close();
}