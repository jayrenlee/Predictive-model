import { Router } from "express";
import { queryFaq } from "../rag/query";
import { getSession } from "../otp/service";

const router = Router();

// POST /api/faq/query
// Body: { question: string, sessionId: string }
// Returns top-K relevant FAQ chunks for the question
router.post("/query", async (req, res) => {
  const { question, sessionId } = req.body as { question?: string; sessionId?: string };

  if (!question) return res.status(400).json({ error: "question required" });
  if (!sessionId) return res.status(401).json({ error: "sessionId required" });

  const session = sessionId ? await getSession(sessionId) : null;
  if (!session || !session.verified) {
    return res.status(403).json({ error: "Session not verified" });
  }

  const chunks = await queryFaq(question, sessionId, session.accountId);
  return res.json({ chunks });
});

export default router;
