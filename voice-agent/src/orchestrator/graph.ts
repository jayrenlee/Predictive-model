import { StateGraph, END } from "@langchain/langgraph";
import { AgentState, AgentStateType } from "./state";
import { routerNode } from "./nodes/router";
import { ragNode } from "./nodes/rag";
import { balanceToolNode, cardLockToolNode, cardUnlockToolNode, loanToolNode } from "./nodes/tools";
import { generateNode, unverifiedNode } from "./nodes/generate";

function routeEdge(state: AgentStateType): string {
  return state.route;
}

export function buildGraph() {
  const graph = new StateGraph(AgentState)
    .addNode("router", routerNode)
    .addNode("unverified", unverifiedNode)
    .addNode("balance_tool", balanceToolNode)
    .addNode("card_lock_tool", cardLockToolNode)
    .addNode("card_unlock_tool", cardUnlockToolNode)
    .addNode("loan_tool", loanToolNode)
    .addNode("rag", ragNode)
    .addNode("generate", generateNode)

    .addEdge("__start__", "router")

    .addConditionalEdges("router", routeEdge, {
      unverified: "unverified",
      balance: "balance_tool",
      card_lock: "card_lock_tool",
      card_unlock: "card_unlock_tool",
      loan: "loan_tool",
      faq: "rag",
    })

    // All tool nodes flow into the LLM response generator
    .addEdge("balance_tool", "generate")
    .addEdge("card_lock_tool", "generate")
    .addEdge("card_unlock_tool", "generate")
    .addEdge("loan_tool", "generate")
    .addEdge("rag", "generate")

    // Terminal nodes
    .addEdge("generate", END)
    .addEdge("unverified", END);

  return graph.compile();
}

// Singleton compiled graph
let _graph: ReturnType<typeof buildGraph> | null = null;
export function getGraph() {
  if (!_graph) _graph = buildGraph();
  return _graph;
}
