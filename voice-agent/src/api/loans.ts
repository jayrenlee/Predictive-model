import { Router } from "express";
import { pool } from "../db/client";
import { auditLog } from "../audit/log";
import { getSession } from "../otp/service";

const router = Router();

// GET /api/loans/:accountId — list all loans for an account
router.get("/:accountId", async (req, res) => {
  const { accountId } = req.params;
  const sessionId = req.headers["x-session-id"] as string | undefined;

  if (!sessionId) return res.status(401).json({ error: "Missing X-Session-Id header" });

  const session = await getSession(sessionId);
  if (!session || !session.verified || session.accountId !== accountId) {
    return res.status(403).json({ error: "Session not verified for this account" });
  }

  const result = await pool.query<{
    loan_id: string;
    loan_type: string;
    outstanding_cents: number;
    next_payment_date: string;
  }>(
    `SELECT loan_id, loan_type, outstanding_cents, next_payment_date
     FROM loans WHERE account_id = $1 ORDER BY next_payment_date`,
    [accountId]
  );

  const loans = result.rows.map((row) => ({
    loanId: row.loan_id,
    loanType: row.loan_type,
    outstanding: (row.outstanding_cents / 100).toFixed(2),
    outstandingCents: row.outstanding_cents,
    nextPaymentDate: row.next_payment_date,
    outstandingDisplay: `MYR ${(row.outstanding_cents / 100).toFixed(2)}`,
  }));

  await auditLog("loan_checked", sessionId, accountId, { loanCount: loans.length });

  return res.json({ loans });
});

export default router;
