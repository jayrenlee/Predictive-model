import { pool } from "../db/client";

export type AuditEventType =
  | "otp_generated"
  | "otp_attempt"
  | "otp_verified"
  | "otp_failed"
  | "otp_expired"
  | "balance_checked"
  | "card_locked"
  | "card_unlocked"
  | "loan_checked"
  | "faq_queried"
  | "session_ended";

export async function auditLog(
  eventType: AuditEventType,
  sessionId: string | null,
  accountId: string | null,
  details?: Record<string, unknown>
): Promise<void> {
  await pool.query(
    `INSERT INTO audit_log (session_id, account_id, event_type, details)
     VALUES ($1, $2, $3, $4)`,
    [sessionId, accountId, eventType, details ? JSON.stringify(details) : null]
  );
}
