import { Router } from "express";
import { pool } from "../db/client";
import { auditLog } from "../audit/log";
import { getSession } from "../otp/service";

const router = Router();

// GET /api/accounts/:accountId/balance
// Requires verified session passed as X-Session-Id header
router.get("/:accountId/balance", async (req, res) => {
  const { accountId } = req.params;
  const sessionId = req.headers["x-session-id"] as string | undefined;

  if (!sessionId) {
    return res.status(401).json({ error: "Missing X-Session-Id header" });
  }

  const session = await getSession(sessionId);
  if (!session || !session.verified || session.accountId !== accountId) {
    return res.status(403).json({ error: "Session not verified for this account" });
  }

  const result = await pool.query<{
    full_name: string;
    balance_cents: number;
    currency: string;
  }>(
    `SELECT full_name, balance_cents, currency FROM accounts WHERE account_id = $1`,
    [accountId]
  );

  if (result.rows.length === 0) {
    return res.status(404).json({ error: "Account not found" });
  }

  const { full_name, balance_cents, currency } = result.rows[0];
  const balanceFormatted = (balance_cents / 100).toFixed(2);

  await auditLog("balance_checked", sessionId, accountId, { currency, balance_cents });

  return res.json({
    accountId,
    fullName: full_name,
    balance: parseFloat(balanceFormatted),
    currency,
    balanceDisplay: `${currency} ${balanceFormatted}`,
  });
});

export default router;
