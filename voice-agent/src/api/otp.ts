import { Router } from "express";
import { pool } from "../db/client";
import { generateOtp, verifyOtp } from "../otp/service";

const router = Router();

// POST /api/otp/generate
// Body: { phoneNumber: string }
// Looks up the account by phone, generates an OTP session
router.post("/generate", async (req, res) => {
  const { phoneNumber } = req.body as { phoneNumber?: string };
  if (!phoneNumber) return res.status(400).json({ error: "phoneNumber required" });

  const result = await pool.query<{ account_id: string; full_name: string }>(
    `SELECT account_id, full_name FROM accounts WHERE phone_number = $1`,
    [phoneNumber]
  );

  if (result.rows.length === 0) {
    return res.status(404).json({ error: "No account found for that phone number" });
  }

  const { account_id, full_name } = result.rows[0];
  const { sessionId } = await generateOtp(account_id);

  // OTP printed to server console — do not return it in the response
  return res.json({ sessionId, accountId: account_id, fullName: full_name });
});

// POST /api/otp/verify
// Body: { sessionId: string, code: string }
router.post("/verify", async (req, res) => {
  const { sessionId, code } = req.body as { sessionId?: string; code?: string };
  if (!sessionId || !code) return res.status(400).json({ error: "sessionId and code required" });

  const result = await verifyOtp(sessionId, code);

  switch (result.status) {
    case "verified":
      return res.json({ verified: true, accountId: result.accountId, sessionId });
    case "invalid":
      return res.status(401).json({ verified: false, reason: "invalid_code", attemptsLeft: result.attemptsLeft });
    case "expired":
      return res.status(401).json({ verified: false, reason: "expired" });
    case "max_attempts":
      return res.status(401).json({ verified: false, reason: "max_attempts" });
    case "not_found":
      return res.status(404).json({ verified: false, reason: "session_not_found" });
  }
});

export default router;
