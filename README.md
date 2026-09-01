# RazorMesh — Agentic Commerce Trust & Payment Layer

> Razorpay AI Buildathon 2026 · Track: AI Growth & Agentic Commerce

## What is RazorMesh?

RazorMesh is a prototype agentic-commerce system where **two cooperating AI agents** — a Buyer Agent and a Merchant Agent — negotiate, transact, and fulfill purchases through a **trust boundary** that ensures every money action is explainable, bounded, gated, and auditable.

The system demonstrates that AI agents can participate in commerce **safely** — the LLM proposes, but deterministic policy engines validate, and only verified code touches money.

## Core Idea

```
USER ↔ Buyer Agent ↔ RazorMesh ACP ↔ Merchant Agent
                          ↓
                   Trust Boundary
                   (Policy Engine + Mandate Verification)
                          ↓
                   Payment Service
                   (Deterministic, Idempotent)
                          ↓
                   Razorpay Test Mode API
                          ↓
                   Audit Trail
                   (Hash-chained, Verifiable)
```

### Key Principle

```
LLM proposes → Policy engine validates → Deterministic code executes → Payment provider confirms
```

**Never:** LLM → Razorpay directly.

## Agents

| Agent | Role |
|-------|------|
| **Buyer Agent** | Conversational shopping assistant. Understands intent, searches catalogs, compares products, requests clarification, proposes purchases within mandate bounds. |
| **Merchant Agent** | Represents a store. Maintains AI-readable catalog, explains products, performs bounded upsell/cross-sell, orchestrates campaigns (coupons, reminders, reviews). |

## Architecture Highlights

- **RazorMesh ACP** — Our lightweight agent-to-agent protocol with structured, typed messages
- **Mandate Model** — AP2-inspired bounded purchase authorization (not fake AP2 — honest prototype)
- **Policy Engine** — Deterministic rule evaluation, no LLM in the validation path
- **Payment Trust Layer** — Idempotent, state-machine-governed payment execution via Razorpay
- **Audit Engine** — Hash-chained event trail for full transaction lifecycle
- **RAG Catalog** — pgvector hybrid search (semantic + structured filters + full-text)
- **LangGraph Workflows** — Stateful agent state machines with human-in-the-loop checkout

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js / React / TypeScript |
| Backend | Python 3.12, FastAPI |
| AI | LangChain, LangGraph |
| Database | PostgreSQL 16 + pgvector |
| Cache/Queue | Redis |
| Validation | Pydantic v2 |
| Payments | Razorpay Test Mode API |
| Testing | pytest, httpx |
| Container | Docker Compose |

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, boundaries, data models, state machines |
| [PROTOCOL.md](docs/PROTOCOL.md) | Agent communication protocol (RazorMesh ACP) |
| [PAYMENTS.md](docs/PAYMENTS.md) | AP2 vs x402 analysis, mandate model, Razorpay integration |
| [SECURITY.md](docs/SECURITY.md) | Trust boundaries, threat model, credential isolation |
| [DEMO_FLOW.md](docs/DEMO_FLOW.md) | End-to-end demo scenario for buildathon pitch |
| [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Phased build plan with vertical slice |

## Status

**Phase: Architecture & Design** — Implementation has not started.

## License

MIT

## Team

Built for the Razorpay AI Buildathon 2026.
