/**
 * RAG ingestion script: reads faq/ directory, chunks text, embeds with
 * all-MiniLM-L6-v2 (CPU-viable, 384-dim), stores in pgvector.
 *
 * Run: npm run ingest
 */

import * as fs from "fs";
import * as path from "path";
import { pool } from "../db/client";

const FAQ_DIR = path.resolve(__dirname, "../../faq");
const CHUNK_SIZE = 400; // characters per chunk
const CHUNK_OVERLAP = 80;

function chunkText(text: string): string[] {
  const chunks: string[] = [];
  let start = 0;
  while (start < text.length) {
    const end = Math.min(start + CHUNK_SIZE, text.length);
    chunks.push(text.slice(start, end).trim());
    start += CHUNK_SIZE - CHUNK_OVERLAP;
  }
  return chunks.filter((c) => c.length > 30);
}

async function ingest() {
  const { pipeline } = await import("@xenova/transformers");
  const pipe = await pipeline("feature-extraction", "Xenova/all-MiniLM-L6-v2");

  const files = fs.readdirSync(FAQ_DIR).filter((f) => f.endsWith(".txt") || f.endsWith(".md"));
  if (files.length === 0) {
    console.error(`No .txt or .md files found in ${FAQ_DIR}`);
    process.exit(1);
  }

  // Clear existing chunks before re-indexing
  await pool.query("DELETE FROM faq_chunks");
  console.log("Cleared existing FAQ chunks.");

  let totalChunks = 0;

  for (const file of files) {
    const content = fs.readFileSync(path.join(FAQ_DIR, file), "utf-8");
    const chunks = chunkText(content);
    console.log(`${file}: ${chunks.length} chunks`);

    for (const chunk of chunks) {
      const output = await pipe(chunk, { pooling: "mean", normalize: true });
      const vector = Array.from(output.data as Float32Array);

      await pool.query(
        `INSERT INTO faq_chunks (content, embedding) VALUES ($1, $2::vector)`,
        [chunk, `[${vector.join(",")}]`]
      );
      totalChunks++;
    }
  }

  console.log(`\nIngestion complete. ${totalChunks} chunks stored.`);
  await pool.end();
}

ingest().catch((err) => {
  console.error(err);
  process.exit(1);
});
