import { AgentStateType } from "../state";
import { queryFaq } from "../../rag/query";

export async function ragNode(state: AgentStateType): Promise<Partial<AgentStateType>> {
  try {
    const chunks = await queryFaq(state.userInput, state.sessionId, state.accountId, 3);
    return { ragContext: chunks };
  } catch {
    // RAG failure is non-fatal — LLM will answer from training knowledge
    return { ragContext: [] };
  }
}
