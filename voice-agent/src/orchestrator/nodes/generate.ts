import { AgentStateType, Turn } from "../state";
import { chat, LlmMessage } from "../../services/llm";
import { auditLog } from "../../audit/log";

const SYSTEM_PROMPT = `You are a helpful, professional banking voice assistant for Viox Bank.
You speak clearly and concisely — responses will be read aloud over a phone call, so keep them under 3 sentences.

Rules you must always follow:
- NEVER invent account balances, card details, loan amounts, or dates. Only use data from tool results provided to you.
- If tool results are empty, say you could not retrieve the information and suggest calling the branch.
- Never repeat the session ID, account ID, or any internal identifiers.
- If the caller hasn't verified their identity, politely ask them to use their keypad to enter their one-time code.
- Always sound human and helpful — no robotic lists. Speak in natural sentences.`.trim();

function toolResultsToContext(state: AgentStateType): string {
  if (state.toolResults.length === 0) return "";
  return "\n\n[TOOL RESULTS]\n" + JSON.stringify(state.toolResults, null, 2);
}

function ragContextToContext(state: AgentStateType): string {
  if (state.ragContext.length === 0) return "";
  return "\n\n[KNOWLEDGE BASE]\n" + state.ragContext.join("\n---\n");
}

export async function generateNode(state: AgentStateType): Promise<Partial<AgentStateType>> {
  const messages: LlmMessage[] = [{ role: "system", content: SYSTEM_PROMPT }];

  // Inject last 6 turns of history for context
  const recentHistory = state.history.slice(-6);
  for (const turn of recentHistory) {
    messages.push({ role: turn.role, content: turn.content });
  }

  // Current user message with any tool/RAG context appended
  const userContent =
    state.userInput +
    toolResultsToContext(state) +
    ragContextToContext(state);

  messages.push({ role: "user", content: userContent });

  const t0 = Date.now();
  const result = await chat(messages);
  const llmMs = Date.now() - t0;

  await auditLog("faq_queried", state.sessionId, state.accountId, {
    route: state.route,
    inputChars: state.userInput.length,
    outputChars: result.text.length,
    llmMs,
    evalTokens: result.eval_count,
    mocked: result.mocked ?? false,
  }).catch(() => {/* non-fatal */});

  const newHistory: Turn[] = [
    { role: "user", content: state.userInput },
    { role: "assistant", content: result.text },
  ];

  return {
    response: result.text,
    history: newHistory,
  };
}

export async function unverifiedNode(state: AgentStateType): Promise<Partial<AgentStateType>> {
  const msg =
    "I'd be happy to help you with that. For your security, please enter your one-time verification code on your keypad to proceed.";
  return {
    response: msg,
    history: [
      { role: "user", content: state.userInput },
      { role: "assistant", content: msg },
    ],
  };
}
