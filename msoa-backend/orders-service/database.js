const Database = require("better-sqlite3");
const path = require("path");

const dbPath = process.env.ORDERS_DB_PATH || path.join(
  __dirname,
  "..",
  "msoa_sqlite_databases",
  "orders",
  "orders.db"
);

const db = new Database(dbPath);
db.pragma("foreign_keys = ON");

console.log("Orders database connected successfully!");

module.exports = db;