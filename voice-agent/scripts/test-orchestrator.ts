/**
 * Phase 3 orchestrator smoke test — no interaction needed.
 * Run: MOCK_AI=true ts-node scripts/test-orchestrator.ts
 */

process.env.MOCK_AI = "true";
import * as dotenv from "dotenv";
dotenv.config();

import { getGraph } from "../src/orchestrator/graph";
import { AgentStateType } from "../src/orchestrator/state";
import { synthesize } from "../src/services/tts";

const SESSION_ID = process.env.TEST_SESSION_ID!;
const ACCOUNT_ID = "a1000000-0000-0000-0000-000000000001";

function pass(label: string) { console.log(`  ✓ ${label}`); }
function fail(label: string, detail?: unknown) { console.error(`  ✗ ${label}`, detail ?? ""); }

async function runTurn(
  graph: ReturnType<typeof getGraph>,
  userInput: string,
  verified: boolean,
  label: string
) {
  const result = await graph.invoke({
    sessionId: SESSION_ID,
    accountId: ACCOUNT_ID,
    callerVerified: verified,
    userInput,
    history: [],
    ragContext: [],
    toolResults: [],
    response: "",
    route: "",
  } satisfies AgentStateType);

  const hasResponse = typeof result.response === "string" && result.response.length > 0;
  hasResponse ? pass(`${label} → "${result.response.slice(0, 70)}..."`) : fail(label, result);

  return result;
}

async function main() {
  if (!SESSION_ID) {
    console.error("Set TEST_SESSION_ID env var to a verified session ID");
    process.exit(1);
  }

  console.log("\n=== Phase 3 Orchestrator Smoke Test (MOCK_AI=true) ===\n");

  const graph = getGraph();

  // 1. Unverified caller
  await runTurn(graph, "what is my balance", false, "Unverified → redirect");

  // 2. Balance query
  await runTurn(graph, "what is my balance", true, "Balance query → tool call");

  // 3. Card lock
  await runTurn(graph, "please lock my card", true, "Card lock → tool call");

  // 4. Card unlock
  await runTurn(graph, "unlock my debit card", true, "Card unlock → tool call");

  // 5. Loan query
  await runTurn(graph, "what's my loan balance and next payment", true, "Loan query → tool call");

  // 6. FAQ (general question)
  await runTurn(graph, "what time does the bank close", true, "FAQ → RAG (may skip if no embeddings)");

  // 7. TTS stub
  console.log("");
  const { audioPath, mocked } = await synthesize("Your balance is twelve thousand ringgit.");
  mocked
    ? pass(`TTS stub WAV written: ${audioPath}`)
    : pass(`TTS real WAV written: ${audioPath}`);

  console.log("\n=== Orchestrator checks complete ===\n");
}

main().catch((err) => { console.error(err); process.exit(1); });
