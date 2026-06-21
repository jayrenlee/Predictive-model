import { Annotation } from "@langchain/langgraph";

// Conversation turn history entry
export interface Turn {
  role: "user" | "assistant";
  content: string;
}

// Banking tool call result attached to a turn
export interface ToolResult {
  tool: string;
  result: Record<string, unknown>;
}

export const AgentState = Annotation.Root({
  // Caller identity (set after OTP verification)
  sessionId: Annotation<string>({ reducer: (_, b) => b }),
  accountId: Annotation<string>({ reducer: (_, b) => b }),
  callerVerified: Annotation<boolean>({ reducer: (_, b) => b }),

  // Current user message (raw transcript or typed text)
  userInput: Annotation<string>({ reducer: (_, b) => b }),

  // Conversation history for LLM context window
  history: Annotation<Turn[]>({
    reducer: (a, b) => [...a, ...b],
    default: () => [],
  }),

  // RAG context retrieved for current turn
  ragContext: Annotation<string[]>({
    reducer: (_, b) => b,
    default: () => [],
  }),

  // Tool calls made this turn
  toolResults: Annotation<ToolResult[]>({
    reducer: (_, b) => b,
    default: () => [],
  }),

  // Final text response to speak/return
  response: Annotation<string>({ reducer: (_, b) => b }),

  // Path taken through the graph (for debug/audit)
  route: Annotation<string>({ reducer: (_, b) => b }),
});

export type AgentStateType = typeof AgentState.State;
