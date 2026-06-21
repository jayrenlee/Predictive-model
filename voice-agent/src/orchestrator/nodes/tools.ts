import * as dotenv from "dotenv";
dotenv.config();

import { AgentStateType, ToolResult } from "../state";
import { auditLog } from "../../audit/log";

const API_BASE = `http://localhost:${process.env.PORT ?? 3000}`;

async function bankRequest<T>(
  method: string,
  path: string,
  sessionId: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "x-session-id": sessionId,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`Bank API ${method} ${path} failed (${res.status}): ${msg}`);
  }
  return res.json() as Promise<T>;
}

export async function balanceToolNode(state: AgentStateType): Promise<Partial<AgentStateType>> {
  const data = await bankRequest<{ balanceDisplay: string; fullName: string; currency: string }>(
    "GET",
    `/api/accounts/${state.accountId}/balance`,
    state.sessionId
  );
  const result: ToolResult = { tool: "get_balance", result: data };
  await auditLog("balance_checked", state.sessionId, state.accountId, { via: "orchestrator" });
  return { toolResults: [result] };
}

export async function cardLockToolNode(state: AgentStateType): Promise<Partial<AgentStateType>> {
  // List cards first to find which one to lock (first unlocked card)
  const { cards } = await bankRequest<{
    cards: { card_id: string; last_four: string; locked: boolean }[];
  }>("GET", `/api/cards/${state.accountId}`, state.sessionId);

  const target = cards.find((c) => !c.locked);
  if (!target) {
    return { toolResults: [{ tool: "card_lock", result: { error: "no_unlocked_cards" } }] };
  }

  const data = await bankRequest<{ cardId: string; lastFour: string; locked: boolean }>(
    "POST",
    `/api/cards/${target.card_id}/lock`,
    state.sessionId
  );
  return { toolResults: [{ tool: "card_lock", result: data }] };
}

export async function cardUnlockToolNode(state: AgentStateType): Promise<Partial<AgentStateType>> {
  const { cards } = await bankRequest<{
    cards: { card_id: string; last_four: string; locked: boolean }[];
  }>("GET", `/api/cards/${state.accountId}`, state.sessionId);

  const target = cards.find((c) => c.locked);
  if (!target) {
    return { toolResults: [{ tool: "card_unlock", result: { error: "no_locked_cards" } }] };
  }

  const data = await bankRequest<{ cardId: string; lastFour: string; locked: boolean }>(
    "POST",
    `/api/cards/${target.card_id}/unlock`,
    state.sessionId
  );
  return { toolResults: [{ tool: "card_unlock", result: data }] };
}

export async function loanToolNode(state: AgentStateType): Promise<Partial<AgentStateType>> {
  const data = await bankRequest<{ loans: unknown[] }>(
    "GET",
    `/api/loans/${state.accountId}`,
    state.sessionId
  );
  return { toolResults: [{ tool: "get_loans", result: data }] };
}
