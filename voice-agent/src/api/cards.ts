import { Router } from "express";
import { pool } from "../db/client";
import { auditLog } from "../audit/log";
import { getSession } from "../otp/service";

const router = Router();

// GET /api/cards/:accountId — list cards for account
router.get("/:accountId", async (req, res) => {
  const { accountId } = req.params;
  const sessionId = req.headers["x-session-id"] as string | undefined;

  if (!sessionId) return res.status(401).json({ error: "Missing X-Session-Id header" });

  const session = await getSession(sessionId);
  if (!session || !session.verified || session.accountId !== accountId) {
    return res.status(403).json({ error: "Session not verified for this account" });
  }

  const result = await pool.query<{ card_id: string; last_four: string; locked: boolean }>(
    `SELECT card_id, last_four, locked FROM cards WHERE account_id = $1 ORDER BY last_four`,
    [accountId]
  );

  return res.json({ cards: result.rows });
});

// POST /api/cards/:cardId/lock
router.post("/:cardId/lock", async (req, res) => {
  const { cardId } = req.params;
  const sessionId = req.headers["x-session-id"] as string | undefined;

  if (!sessionId) return res.status(401).json({ error: "Missing X-Session-Id header" });

  const cardResult = await pool.query<{ account_id: string; last_four: string; locked: boolean }>(
    `SELECT account_id, last_four, locked FROM cards WHERE card_id = $1`,
    [cardId]
  );

  if (cardResult.rows.length === 0) return res.status(404).json({ error: "Card not found" });

  const card = cardResult.rows[0];
  const session = await getSession(sessionId);
  if (!session || !session.verified || session.accountId !== card.account_id) {
    return res.status(403).json({ error: "Session not verified for this account" });
  }

  await pool.query(`UPDATE cards SET locked = true WHERE card_id = $1`, [cardId]);
  await auditLog("card_locked", sessionId, card.account_id, { cardId, lastFour: card.last_four });

  return res.json({ cardId, lastFour: card.last_four, locked: true });
});

// POST /api/cards/:cardId/unlock
router.post("/:cardId/unlock", async (req, res) => {
  const { cardId } = req.params;
  const sessionId = req.headers["x-session-id"] as string | undefined;

  if (!sessionId) return res.status(401).json({ error: "Missing X-Session-Id header" });

  const cardResult = await pool.query<{ account_id: string; last_four: string; locked: boolean }>(
    `SELECT account_id, last_four, locked FROM cards WHERE card_id = $1`,
    [cardId]
  );

  if (cardResult.rows.length === 0) return res.status(404).json({ error: "Card not found" });

  const card = cardResult.rows[0];
  const session = await getSession(sessionId);
  if (!session || !session.verified || session.accountId !== card.account_id) {
    return res.status(403).json({ error: "Session not verified for this account" });
  }

  await pool.query(`UPDATE cards SET locked = false WHERE card_id = $1`, [cardId]);
  await auditLog("card_unlocked", sessionId, card.account_id, { cardId, lastFour: card.last_four });

  return res.json({ cardId, lastFour: card.last_four, locked: false });
});

export default router;
