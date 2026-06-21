import { AgentStateType } from "../state";

const BALANCE_PATTERNS = /\b(balance|how much|money|funds?|amount)\b/i;
const CARD_LOCK_PATTERNS = /\b(lock|freeze|block)\b.{0,20}\b(card|debit|credit)\b/i;
const CARD_UNLOCK_PATTERNS = /\b(unlock|unfreeze|unblock|activate)\b.{0,20}\b(card|debit|credit)\b/i;
const LOAN_PATTERNS = /\b(loan|loan balance|repay|outstanding|payment due|next payment)\b/i;
const CARD_LIST_PATTERNS = /\b(my cards?|card number|card details?|which card)\b/i;

export type RouteType = "unverified" | "balance" | "card_lock" | "card_unlock" | "loan" | "faq";

export function classifyIntent(input: string): RouteType {
  const t = input.toLowerCase();
  if (BALANCE_PATTERNS.test(t)) return "balance";
  if (CARD_LOCK_PATTERNS.test(t)) return "card_lock";
  if (CARD_UNLOCK_PATTERNS.test(t)) return "card_unlock";
  if (LOAN_PATTERNS.test(t)) return "loan";
  if (CARD_LIST_PATTERNS.test(t)) return "loan"; // reuses loan node for card listing; handled in tools
  return "faq";
}

export function routerNode(state: AgentStateType): Partial<AgentStateType> {
  if (!state.callerVerified) {
    return { route: "unverified" };
  }
  const route = classifyIntent(state.userInput);
  return { route };
}
