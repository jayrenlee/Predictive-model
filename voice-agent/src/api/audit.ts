import { Router } from "express";
import { pool } from "../db/client";

const router = Router();

// GET /api/audit/sessions — recent sessions (last 50)
router.get("/sessions", async (_req, res) => {
  const result = await pool.query<{
    session_id: string;
    account_id: string;
    full_name: string;
    verified: boolean;
    created_at: Date;
    event_count: number;
  }>(`
    SELECT
      o.session_id,
      o.account_id,
      a.full_name,
      o.verified,
      o.created_at,
      COUNT(l.log_id)::int AS event_count
    FROM otp_sessions o
    LEFT JOIN accounts a ON a.account_id = o.account_id
    LEFT JOIN audit_log l ON l.session_id = o.session_id
    GROUP BY o.session_id, o.account_id, a.full_name, o.verified, o.created_at
    ORDER BY o.created_at DESC
    LIMIT 50
  `);
  return res.json({ sessions: result.rows });
});

// GET /api/audit/:sessionId — full event trail for one session
router.get("/:sessionId", async (req, res) => {
  const { sessionId } = req.params;

  const sessionResult = await pool.query<{
    account_id: string;
    full_name: string;
    phone_number: string;
    verified: boolean;
    attempts: number;
    created_at: Date;
    expires_at: Date;
  }>(`
    SELECT o.account_id, a.full_name, a.phone_number,
           o.verified, o.attempts, o.created_at, o.expires_at
    FROM otp_sessions o
    JOIN accounts a ON a.account_id = o.account_id
    WHERE o.session_id = $1
  `, [sessionId]);

  if (!sessionResult.rows.length) {
    return res.status(404).json({ error: "Session not found" });
  }

  const eventsResult = await pool.query<{
    log_id: string;
    event_type: string;
    details: unknown;
    created_at: Date;
  }>(`
    SELECT log_id, event_type, details, created_at
    FROM audit_log
    WHERE session_id = $1
    ORDER BY created_at ASC
  `, [sessionId]);

  return res.json({
    session: { sessionId, ...sessionResult.rows[0] },
    events: eventsResult.rows,
  });
});

// GET /audit — simple HTML viewer
router.get("/", (_req, res) => {
  const html = [
    "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>",
    "<title>Viox — Audit Log</title>",
    "<style>",
    "body{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:20px}",
    "h1{color:#58a6ff}table{border-collapse:collapse;width:100%;margin-top:12px}",
    "th{background:#161b22;color:#8b949e;text-align:left;padding:8px}",
    "td{padding:8px;border-bottom:1px solid #21262d}a{color:#58a6ff}",
    ".ok{color:#3fb950}.fail{color:#f85149}",
    "#detail{margin-top:24px;white-space:pre;background:#161b22;padding:16px;border-radius:6px}",
    "</style></head><body>",
    "<h1>Viox Bank — Audit Log Viewer</h1>",
    "<div id='sessions'>Loading…</div>",
    "<div id='detail'></div>",
    "<script>",
    "async function load(){",
    "  const r=await fetch('/api/audit/sessions');",
    "  const {sessions}=await r.json();",
    "  let rows='';",
    "  for(const s of sessions){",
    "    const sid=s.session_id;",
    "    const st=s.verified?'<span class=ok>&#10003; verified</span>':'<span class=fail>&#10007; unverified</span>';",
    "    rows+=`<tr><td><a href='#' onclick='loadSession(\"${sid}\");return false'>${sid.slice(0,8)}…</a></td>",
    "      <td>${s.full_name||'—'}</td><td>${st}</td><td>${s.event_count} events</td>",
    "      <td>${new Date(s.created_at).toLocaleString()}</td></tr>`;",
    "  }",
    "  document.getElementById('sessions').innerHTML=",
    "    '<table><tr><th>Session</th><th>Account</th><th>Status</th><th>Events</th><th>Started</th></tr>'+rows+'</table>';",
    "}",
    "async function loadSession(id){",
    "  const r=await fetch('/api/audit/'+id);",
    "  const data=await r.json();",
    "  document.getElementById('detail').textContent=JSON.stringify(data,null,2);",
    "}",
    "load();",
    "</script></body></html>",
  ].join("\n");
  res.type("html").send(html);
});

export default router;
