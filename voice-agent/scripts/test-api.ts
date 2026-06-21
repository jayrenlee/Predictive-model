/**
 * Phase 1 smoke test — exercises the mock bank API end-to-end with plain HTTP.
 * Run: npm run test:api  (requires the server to be running on PORT 3000)
 */

const BASE = `http://localhost:${process.env.PORT ?? 3000}`;

async function req(method: string, path: string, body?: unknown, headers?: Record<string, string>) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...headers },
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = await res.json().catch(() => null);
  return { status: res.status, body: json };
}

function pass(label: string) { console.log(`  ✓ ${label}`); }
function fail(label: string, detail: unknown) { console.error(`  ✗ ${label}`, detail); }

async function run() {
  console.log("\n=== Viox Voice Agent — Phase 1 API Smoke Test ===\n");

  // 1. Health check
  {
    const r = await req("GET", "/health");
    r.status === 200 ? pass("Health check") : fail("Health check", r);
  }

  // 2. Generate OTP for Jayren Lee
  let sessionId = "";
  let accountId = "";
  {
    const r = await req("POST", "/api/otp/generate", { phoneNumber: "+60123456789" });
    if (r.status === 200 && r.body.sessionId) {
      pass(`OTP generated — sessionId: ${r.body.sessionId}`);
      sessionId = r.body.sessionId;
      accountId = r.body.accountId;
      console.log(`     >>> Check server console for OTP code <<<`);
    } else {
      fail("OTP generate", r);
      process.exit(1);
    }
  }

  // 3. Try wrong OTP
  {
    const r = await req("POST", "/api/otp/verify", { sessionId, code: "000000" });
    r.status === 401 && r.body.reason === "invalid_code"
      ? pass(`Wrong OTP rejected (${r.body.attemptsLeft} attempts left)`)
      : fail("Wrong OTP should be rejected", r);
  }

  // Prompt user for correct OTP (from server console)
  const readline = require("readline");
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const code: string = await new Promise((resolve) => {
    rl.question("\n  Enter the OTP from server console: ", (ans: string) => { rl.close(); resolve(ans.trim()); });
  });

  // 4. Verify correct OTP
  {
    const r = await req("POST", "/api/otp/verify", { sessionId, code });
    if (r.status === 200 && r.body.verified) {
      pass("OTP verified successfully");
    } else {
      fail("OTP verify", r);
      process.exit(1);
    }
  }

  const authHeaders = { "x-session-id": sessionId };

  // 5. Balance check
  {
    const r = await req("GET", `/api/accounts/${accountId}/balance`, undefined, authHeaders);
    r.status === 200 && r.body.balance
      ? pass(`Balance: ${r.body.balanceDisplay}`)
      : fail("Balance check", r);
  }

  // 6. List cards
  let cardId = "";
  {
    const r = await req("GET", `/api/cards/${accountId}`, undefined, authHeaders);
    if (r.status === 200 && r.body.cards?.length) {
      pass(`Cards found: ${r.body.cards.map((c: { last_four: string; locked: boolean }) => `****${c.last_four} (${c.locked ? "locked" : "unlocked"})`).join(", ")}`);
      cardId = r.body.cards[0].card_id;
    } else {
      fail("List cards", r);
    }
  }

  // 7. Lock first card
  if (cardId) {
    const r = await req("POST", `/api/cards/${cardId}/lock`, undefined, authHeaders);
    r.status === 200 && r.body.locked === true
      ? pass(`Card ****${r.body.lastFour} locked`)
      : fail("Lock card", r);
  }

  // 8. Unlock it again
  if (cardId) {
    const r = await req("POST", `/api/cards/${cardId}/unlock`, undefined, authHeaders);
    r.status === 200 && r.body.locked === false
      ? pass(`Card ****${r.body.lastFour} unlocked`)
      : fail("Unlock card", r);
  }

  // 9. Loans
  {
    const r = await req("GET", `/api/loans/${accountId}`, undefined, authHeaders);
    if (r.status === 200 && r.body.loans?.length) {
      pass(`Loans found:`);
      for (const l of r.body.loans) {
        console.log(`     - ${l.loanType}: ${l.outstandingDisplay} outstanding, next payment ${l.nextPaymentDate}`);
      }
    } else {
      fail("Loans", r);
    }
  }

  // 10. Unauthenticated request should fail
  {
    const r = await req("GET", `/api/accounts/${accountId}/balance`);
    r.status === 401
      ? pass("Unauthenticated request correctly rejected")
      : fail("Unauthenticated should be 401", r);
  }

  console.log("\n=== All Phase 1 checks complete ===\n");
}

run().catch((err) => { console.error(err); process.exit(1); });
