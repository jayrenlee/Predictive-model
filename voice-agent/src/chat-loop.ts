/**
 * Phase 3 text-only chat loop.
 * Simulates a full conversation turn: route → tool/RAG → LLM response → TTS.
 * No telephony needed — type messages, get spoken responses (WAV written to /tmp/).
 *
 * Usage:
 *   MOCK_AI=true ts-node src/chat-loop.ts          # fully mocked, no GPU needed
 *   ts-node src/chat-loop.ts                        # real Ollama + TTS (GPU box must be running)
 */

import * as readline from "readline";
import * as dotenv from "dotenv";
dotenv.config();

import { getGraph } from "./orchestrator/graph";
import { AgentStateType, Turn } from "./orchestrator/state";
import { synthesize } from "./services/tts";
import { generateOtp, verifyOtp } from "./otp/service";
import { pool } from "./db/client";

const MOCK_AI = process.env.MOCK_AI === "true";

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (q: string): Promise<string> =>
  new Promise((resolve) => rl.question(q, (a) => resolve(a.trim())));

async function main() {
  console.log("\n=== Viox Banking Voice Agent — Text Chat Loop ===");
  console.log(`Mode: ${MOCK_AI ? "MOCK (no GPU required)" : "LIVE (GPU box endpoints)"}\n`);

  // ── Step 1: identify caller by phone number ───────────────────────────────
  const phone = await ask("Phone number (+601...): ");
  const accountResult = await pool.query<{ account_id: string; full_name: string }>(
    "SELECT account_id, full_name FROM accounts WHERE phone_number = $1",
    [phone]
  );
  if (!accountResult.rows.length) {
    console.error("No account found for that number.");
    process.exit(1);
  }
  const { account_id: accountId, full_name } = accountResult.rows[0];
  console.log(`\nAccount found: ${full_name} (${accountId})`);

  // ── Step 2: OTP verification ──────────────────────────────────────────────
  const { sessionId, otpCode } = await generateOtp(accountId);
  console.log(`\n[OTP sent to console — in real call this goes via DTMF]`);
  console.log(`OTP code: ${otpCode}\n`);

  let verified = false;
  for (let attempt = 1; attempt <= 3; attempt++) {
    const entered = await ask(`Enter OTP (attempt ${attempt}/3): `);
    const result = await verifyOtp(sessionId, entered);
    if (result.status === "verified") {
      verified = true;
      console.log("Identity verified. You may now ask banking questions.\n");
      break;
    } else if (result.status === "invalid") {
      console.log(`Wrong code. ${result.attemptsLeft} attempt(s) left.`);
    } else {
      console.log(`Verification failed: ${result.status}. Session ended.`);
      process.exit(1);
    }
  }
  if (!verified) {
    console.log("Too many failed attempts. Session terminated.");
    process.exit(1);
  }

  // ── Step 3: conversation loop ─────────────────────────────────────────────
  const graph = getGraph();
  let history: Turn[] = [];

  console.log('Type your banking question (or "quit" to exit).\n');

  while (true) {
    const userInput = await ask("You: ");
    if (!userInput || userInput.toLowerCase() === "quit") break;

    const t0 = Date.now();

    const result = await graph.invoke({
      sessionId,
      accountId,
      callerVerified: verified,
      userInput,
      history,
      ragContext: [],
      toolResults: [],
      response: "",
      route: "",
    } satisfies AgentStateType);

    const elapsed = Date.now() - t0;
    history = result.history as Turn[];

    console.log(`\nAgent [${elapsed}ms]: ${result.response}\n`);

    // Synthesize to audio
    const { audioPath, mocked } = await synthesize(result.response);
    console.log(`Audio: ${audioPath}${mocked ? " (stub — no TTS endpoint)" : ""}`);
    console.log("       Play with: aplay " + audioPath + "\n");
  }

  await pool.end();
  rl.close();
  console.log("Session ended.");
}

main().catch((err) => { console.error(err); process.exit(1); });
