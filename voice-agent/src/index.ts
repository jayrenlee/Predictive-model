import express from "express";
import * as dotenv from "dotenv";
dotenv.config();

import accountsRouter from "./api/accounts";
import cardsRouter from "./api/cards";
import loansRouter from "./api/loans";
import otpRouter from "./api/otp";
import faqRouter from "./api/faq";
import agentRouter from "./api/agent";
import auditRouter from "./api/audit";

const app = express();
app.use(express.json());

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", ts: new Date().toISOString() });
});

// Mock bank API routes
app.use("/api/accounts", accountsRouter);
app.use("/api/cards", cardsRouter);
app.use("/api/loans", loansRouter);
app.use("/api/otp", otpRouter);
app.use("/api/faq", faqRouter);
app.use("/api/agent", agentRouter);
app.use("/api/audit", auditRouter);
app.use("/audit", auditRouter);

const PORT = Number(process.env.PORT ?? 3000);
app.listen(PORT, () => {
  console.log(`Viox Banking Voice Agent API running on port ${PORT}`);
});

export default app;
