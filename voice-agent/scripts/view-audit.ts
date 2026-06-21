/**
 * CLI audit log viewer.
 * Usage:
 *   ts-node scripts/view-audit.ts                   # list last 20 sessions
 *   ts-node scripts/view-audit.ts <session-id>      # full trail for one session
 */

import * as dotenv from "dotenv";
dotenv.config();
import { pool } from "../src/db/client";

const BOLD = "\x1b[1m";
const GREEN = "\x1b[32m";
const RED = "\x1b[31m";
const CYAN = "\x1b[36m";
const DIM = "\x1b[2m";
const RESET = "\x1b[0m";

function fmt(d: Date | string) {
  return new Date(d).toISOString().replace("T", " ").slice(0, 19);
}

async function listSessions() {
  const result = await pool.query<{
    session_id: string;
    full_name: string;
    phone_number: string;
    verified: boolean;
    attempts: number;
    created_at: Date;
    event_count: number;
  }>(`
    SELECT o.session_id, a.full_name, a.phone_number,
           o.verified, o.attempts, o.created_at,
           COUNT(l.log_id)::int AS event_count
    FROM otp_sessions o
    LEFT JOIN accounts a ON a.account_id = o.account_id
    LEFT JOIN audit_log l ON l.session_id = o.session_id
    GROUP BY o.session_id, a.full_name, a.phone_number, o.verified, o.attempts, o.created_at
    ORDER BY o.created_at DESC
    LIMIT 20
  `);

  console.log(`\n${BOLD}Recent sessions (last 20):${RESET}\n`);
  for (const row of result.rows) {
    const status = row.verified
      ? `${GREEN}✓ verified${RESET}`
      : `${RED}✗ unverified${RESET}`;
    console.log(
      `  ${CYAN}${row.session_id.slice(0, 8)}…${RESET}` +
      `  ${row.full_name?.padEnd(16) ?? "(unknown)".padEnd(16)}` +
      `  ${row.phone_number ?? ""}`.padEnd(16) +
      `  ${status}  ` +
      `${DIM}${row.event_count} events  ${fmt(row.created_at)}${RESET}`
    );
  }
  console.log("");
}

async function showSession(sessionId: string) {
  // Allow full UUID or a prefix (at least 8 hex chars)
  const isFullUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(sessionId);

  if (!isFullUuid) {
    const partial = await pool.query<{ session_id: string }>(
      "SELECT session_id FROM otp_sessions WHERE session_id::text LIKE $1 || '%' LIMIT 1",
      [sessionId]
    );
    if (!partial.rows.length) {
      console.error(`Session not found: ${sessionId}`);
      process.exit(1);
    }
    return showSession(partial.rows[0].session_id);
  }

  const session = await pool.query(`
    SELECT o.session_id, o.account_id, a.full_name, a.phone_number,
           o.verified, o.attempts, o.created_at, o.expires_at
    FROM otp_sessions o JOIN accounts a ON a.account_id = o.account_id
    WHERE o.session_id = $1
  `, [sessionId]);

  if (!session.rows.length) {
    console.error(`Session not found: ${sessionId}`);
    process.exit(1);
  }

  const s = session.rows[0];
  const status = s.verified ? `${GREEN}VERIFIED${RESET}` : `${RED}UNVERIFIED${RESET}`;

  console.log(`\n${BOLD}Session: ${s.session_id}${RESET}`);
  console.log(`  Account  : ${s.full_name} (${s.phone_number})`);
  console.log(`  Status   : ${status}  (${s.attempts} OTP attempt(s))`);
  console.log(`  Started  : ${fmt(s.created_at)}`);
  console.log(`  Expires  : ${fmt(s.expires_at)}\n`);

  const events = await pool.query<{
    event_type: string;
    details: unknown;
    created_at: Date;
  }>(
    "SELECT event_type, details, created_at FROM audit_log WHERE session_id = $1 ORDER BY created_at",
    [s.session_id]
  );

  console.log(`${BOLD}Event trail (${events.rows.length} events):${RESET}\n`);
  for (const ev of events.rows) {
    const detail = ev.details ? JSON.stringify(ev.details) : "";
    console.log(
      `  ${DIM}${fmt(ev.created_at)}${RESET}  ` +
      `${CYAN}${ev.event_type.padEnd(20)}${RESET}  ` +
      `${DIM}${detail}${RESET}`
    );
  }
  console.log("");
}

async function main() {
  const arg = process.argv[2];
  try {
    if (arg) {
      await showSession(arg);
    } else {
      await listSessions();
      console.log(`Tip: pass a session ID prefix to see its full event trail.\n`);
    }
  } finally {
    await pool.end();
  }
}

main().catch((err) => { console.error(err); process.exit(1); });
