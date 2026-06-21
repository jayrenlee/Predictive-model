import { Router } from "express";
import { getSession } from "../otp/service";
import { getGraph } from "../orchestrator/graph";
import { AgentStateType } from "../orchestrator/state";

const router = Router();

// POST /api/agent/turn
// Called by the LiveKit Python agent on each verified voice turn.
// Body: { sessionId, accountId, userInput }
// Returns: { response, route, turnMs }
router.post("/turn", async (req, res) => {
  const { sessionId, accountId, userInput } = req.body as {
    sessionId?: string;
    accountId?: string;
    userInput?: string;
  };

  if (!sessionId || !accountId || !userInput) {
    return res.status(400).json({ error: "sessionId, accountId, and userInput required" });
  }

  const session = await getSession(sessionId);
  if (!session || !session.verified) {
    return res.status(403).json({ error: "Session not verified" });
  }
  if (session.accountId !== accountId) {
    return res.status(403).json({ error: "accountId mismatch" });
  }

  const t0 = Date.now();
  const graph = getGraph();

  const result = await graph.invoke({
    sessionId,
    accountId,
    callerVerified: true,
    userInput,
    history: [],       // history is managed per-call in agent.py via conversation context
    ragContext: [],
    toolResults: [],
    response: "",
    route: "",
  } satisfies AgentStateType);

  return res.json({
    response: result.response,
    route: result.route,
    turnMs: Date.now() - t0,
  });
});

export default router;
