import { Pool } from "pg";
import * as dotenv from "dotenv";
dotenv.config();

export const pool = new Pool({
  host: process.env.POSTGRES_HOST ?? "localhost",
  port: Number(process.env.POSTGRES_PORT ?? 5432),
  user: process.env.POSTGRES_USER ?? "viox",
  password: process.env.POSTGRES_PASSWORD ?? "voiceagent",
  database: process.env.POSTGRES_DB ?? "banking",
});

pool.on("error", (err) => {
  console.error("Postgres pool error:", err);
});
