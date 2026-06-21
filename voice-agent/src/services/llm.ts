import * as dotenv from "dotenv";
dotenv.config();

const OLLAMA_URL = process.env.OLLAMA_URL ?? "http://localhost:11434";
const OLLAMA_MODEL = process.env.OLLAMA_MODEL ?? "llama3.1:8b-instruct-q4_K_M";
const MOCK_AI = process.env.MOCK_AI === "true";

export interface LlmMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface LlmResult {
  text: string;
  eval_count?: number;
  duration_ms?: number;
  mocked?: boolean;
}

export async function chat(messages: LlmMessage[]): Promise<LlmResult> {
  if (MOCK_AI) {
    const userMsgs = messages.filter((m: LlmMessage) => m.role === "user");
    const last = userMsgs[userMsgs.length - 1]?.content ?? "";
    return {
      text: `[MOCK LLM] You asked: "${last.slice(0, 60)}". This is a stub response for local testing.`,
      mocked: true,
    };
  }

  const t0 = Date.now();
  const res = await fetch(`${OLLAMA_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: OLLAMA_MODEL, messages, stream: false }),
  });

  if (!res.ok) throw new Error(`Ollama error ${res.status}: ${await res.text()}`);

  const data = (await res.json()) as {
    message: { content: string };
    eval_count?: number;
  };

  return {
    text: data.message.content.trim(),
    eval_count: data.eval_count,
    duration_ms: Date.now() - t0,
  };
}
