import { pool } from "../db/client";
import { auditLog } from "../audit/log";
import * as crypto from "crypto";
import * as dotenv from "dotenv";
dotenv.config();

const OTP_EXPIRY_SECONDS = Number(process.env.OTP_EXPIRY_SECONDS ?? 120);
const OTP_MAX_ATTEMPTS = Number(process.env.OTP_MAX_ATTEMPTS ?? 3);

export interface OtpSession {
  sessionId: string;
  accountId: string;
  verified: boolean;
  attempts: number;
  expiresAt: Date;
}

export async function generateOtp(accountId: string): Promise<{ sessionId: string; otpCode: string }> {
  const otpCode = crypto.randomInt(100000, 999999).toString();
  const expiresAt = new Date(Date.now() + OTP_EXPIRY_SECONDS * 1000);

  const result = await pool.query<{ session_id: string }>(
    `INSERT INTO otp_sessions (account_id, otp_code, expires_at)
     VALUES ($1, $2, $3)
     RETURNING session_id`,
    [accountId, otpCode, expiresAt]
  );

  const sessionId = result.rows[0].session_id;
  await auditLog("otp_generated", sessionId, accountId, { expiresAt });

  // In production this would go via SMS; for demo it prints to console
  console.log(`[OTP] Session ${sessionId} — code: ${otpCode} (expires ${expiresAt.toISOString()})`);

  return { sessionId, otpCode };
}

export type VerifyResult =
  | { status: "verified"; sessionId: string; accountId: string }
  | { status: "invalid"; attemptsLeft: number }
  | { status: "expired" }
  | { status: "max_attempts" }
  | { status: "not_found" };

export async function verifyOtp(sessionId: string, enteredCode: string): Promise<VerifyResult> {
  const result = await pool.query<{
    account_id: string;
    otp_code: string;
    attempts: number;
    verified: boolean;
    expires_at: Date;
  }>(
    `SELECT account_id, otp_code, attempts, verified, expires_at
     FROM otp_sessions WHERE session_id = $1`,
    [sessionId]
  );

  if (result.rows.length === 0) return { status: "not_found" };

  const row = result.rows[0];

  if (new Date() > row.expires_at) {
    await auditLog("otp_expired", sessionId, row.account_id);
    return { status: "expired" };
  }

  if (row.attempts >= OTP_MAX_ATTEMPTS) {
    return { status: "max_attempts" };
  }

  await pool.query(
    `UPDATE otp_sessions SET attempts = attempts + 1 WHERE session_id = $1`,
    [sessionId]
  );

  if (enteredCode !== row.otp_code) {
    const attemptsLeft = OTP_MAX_ATTEMPTS - (row.attempts + 1);
    await auditLog("otp_attempt", sessionId, row.account_id, {
      success: false,
      attemptsLeft,
    });
    if (attemptsLeft <= 0) {
      return { status: "max_attempts" };
    }
    return { status: "invalid", attemptsLeft };
  }

  await pool.query(
    `UPDATE otp_sessions SET verified = true WHERE session_id = $1`,
    [sessionId]
  );
  await auditLog("otp_verified", sessionId, row.account_id);

  return { status: "verified", sessionId, accountId: row.account_id };
}

export async function getSession(sessionId: string): Promise<OtpSession | null> {
  const result = await pool.query<OtpSession>(
    `SELECT session_id as "sessionId", account_id as "accountId",
            verified, attempts, expires_at as "expiresAt"
     FROM otp_sessions WHERE session_id = $1`,
    [sessionId]
  );
  return result.rows[0] ?? null;
}
