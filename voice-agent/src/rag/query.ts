import { pool } from "../db/client";
import { auditLog } from "../audit/log";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type EmbedFn = (text: string, opts?: Record<string, unknown>) => Promise<any>;
let embedder: EmbedFn | null = null;

async function getEmbedder(): Promise<EmbedFn> {
  if (!embedder) {
    const { pipeline } = await import("@xenova/transformers");
    const pipe = await pipeline("feature-extraction", "Xenova/all-MiniLM-L6-v2");
    embedder = (text: string, opts?: Record<string, unknown>) => pipe(text, opts);
  }
  return embedder;
}

export async function queryFaq(
  question: string,
  sessionId: string | null,
  accountId: string | null,
  topK = 3
): Promise<string[]> {
  const embed = await getEmbedder();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const output: any = await embed(question, { pooling: "mean", normalize: true });
  const vector = Array.from(output.data as Float32Array);

  const result = await pool.query<{ content: string; distance: number }>(
    `SELECT content, embedding <-> $1::vector AS distance
     FROM faq_chunks
     ORDER BY distance ASC
     LIMIT $2`,
    [`[${vector.join(",")}]`, topK]
  );

  await auditLog("faq_queried", sessionId, accountId, {
    question: question.slice(0, 100),
    resultsFound: result.rows.length,
  });

  return result.rows.map((r) => r.content);
}
