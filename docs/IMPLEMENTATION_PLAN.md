# RazorMesh Implementation Plan

> Phased build plan from architecture to working demo.  
> Deadline: September 5, 2026 (Razorpay AI Buildathon)

---

## 1. Build Philosophy

- **Vertical slice first** — Get one path working end-to-end before widening
- **Real APIs from day 1** — Razorpay Test Mode, not mock responses
- **Honest labeling** — Every simulated component is clearly marked
- **Test alongside build** — Policy engine and payment state machine tested immediately
- **UI last** — Backend + agents first, frontend is polish

---

## 2. Phase Overview

| Phase | Duration | Deliverable | Risk Level |
|-------|----------|-------------|------------|
| **Phase 1: Foundation** | 1 day | Database, models, config, Razorpay adapter | Low |
| **Phase 2: Trust Boundary** | 1 day | Policy engine, mandate service, payment service, audit engine | Medium |
| **Phase 3: Agents & RAG** | 1.5 days | Buyer agent, merchant agent, catalog RAG, ACP router | High |
| **Phase 4: Integration** | 1 day | End-to-end flow, LangGraph HITL checkout, webhooks | High |
| **Phase 5: Frontend** | 1 day | Chat UI, checkout, audit viewer | Medium |
| **Phase 6: Polish & Demo** | 0.5 days | Demo script, failure scenario, pitch video | Low |

**Total: ~6 days** (fits within the remaining window to Sept 5)

---

## 3. Phase 1: Foundation (Day 1)

### Goal
Infrastructure that everything else builds on.

### Tasks

#### 1.1 Project Setup
- [ ] Initialize `pyproject.toml` with dependencies:
  ```
  fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic,
  langchain, langgraph, langchain-openai, langchain-community,
  pydantic, pydantic-settings, razorpay, redis, pgvector,
  structlog, httpx, pytest, pytest-asyncio
  ```
- [ ] Create `docker-compose.yml` (PostgreSQL 16 + pgvector, Redis)
- [ ] Create `.env.example` with all required variables
- [ ] Create `.gitignore` (Python, Node, .env, IDE)

#### 1.2 Database Setup
- [ ] PostgreSQL schema: `products`, `users`, `mandates`, `orders`, `payments`, `audit_events`, `campaigns`, `idempotency_store`
- [ ] pgvector extension enabled
- [ ] Alembic initial migration
- [ ] Seed script with demo products (10-15 mechanical keyboards, electronics)

#### 1.3 Core Models (Pydantic)
- [ ] `models/catalog.py` — Product, ProductSearchQuery, ProductSearchResult
- [ ] `models/mandate.py` — Mandate, MandateConstraints, MandateStatus
- [ ] `models/order.py` — Order, OrderItem, OrderStatus
- [ ] `models/payment.py` — PaymentIntent, PaymentResult, PaymentStatus
- [ ] `models/protocol.py` — MessageEnvelope, MessageType, all payloads
- [ ] `models/audit.py` — AuditEvent, EventType
- [ ] `models/campaign.py` — Campaign, CampaignAction, CampaignStatus

#### 1.4 Razorpay Adapter
- [ ] `adapters/razorpay_adapter.py` — ONLY file importing razorpay SDK
- [ ] `create_order()` — POST /v1/orders
- [ ] `fetch_order()` — GET /v1/orders/{id}
- [ ] `fetch_payment()` — GET /v1/payments/{id}
- [ ] `verify_payment_signature()` — HMAC-SHA256
- [ ] `verify_webhook_signature()` — HMAC-SHA256
- [ ] Integration test: create a real test-mode order

#### 1.5 Configuration
- [ ] `core/config.py` — Pydantic Settings loading from `.env`
- [ ] `core/database.py` — asyncpg pool setup
- [ ] `core/redis.py` — Redis client

### Verification
- [ ] `docker-compose up` starts PostgreSQL + Redis
- [ ] Alembic migration runs successfully
- [ ] Seed script populates products
- [ ] Razorpay adapter creates a test order via API
- [ ] All Pydantic models validate correctly

---

## 4. Phase 2: Trust Boundary (Day 2)

### Goal
The deterministic layer between AI and money. This is the core of the buildathon demo.

### Tasks

#### 2.1 Mandate Service
- [ ] `services/mandate_service.py`
- [ ] Create mandate (user-initiated, HMAC-signed)
- [ ] Verify mandate against PaymentIntent (deterministic)
- [ ] Update mandate usage (amount_used_paise)
- [ ] Expire/revoke mandates
- [ ] **Unit tests**: all edge cases (expired, over-budget, wrong merchant, duplicate)

#### 2.2 Policy Engine
- [ ] `services/policy_engine.py`
- [ ] Rule: budget limit per transaction
- [ ] Rule: daily aggregate limit
- [ ] Rule: mandate coverage verification
- [ ] Rule: merchant/category allowlist
- [ ] Rule: duplicate idempotency check
- [ ] Rule: rate limit (attempts per hour)
- [ ] Rule: price drift (offered vs catalog price)
- [ ] Returns `PolicyResult(decision, reasons, evaluated_rules)`
- [ ] **Unit tests**: every rule individually + combinations

#### 2.3 Payment Service
- [ ] `services/payment_service.py`
- [ ] Payment state machine with explicit valid transitions
- [ ] `initiate_payment()`: mandate check → policy check → Razorpay order creation
- [ ] `confirm_payment()`: signature verification → order confirmation
- [ ] `handle_payment_failure()`: state transition + audit
- [ ] Idempotency enforcement on all operations
- [ ] **Unit tests**: all state transitions, invalid transition rejection

#### 2.4 Order Service
- [ ] `services/order_service.py`
- [ ] Order state machine (pending → confirmed → accepted → processing → completed)
- [ ] Create order from confirmed payment
- [ ] Fulfilment gap handling: payment OK but order fails → reconciliation

#### 2.5 Audit Engine
- [ ] `services/audit_service.py`
- [ ] Append-only event logging to PostgreSQL
- [ ] Hash chain: each event includes SHA-256 of previous event
- [ ] `log_event()` — standard interface used by all services
- [ ] `verify_chain()` — validate integrity of event sequence
- [ ] `get_trail()` — retrieve audit trail for an entity
- [ ] **Unit tests**: chain integrity, tamper detection

#### 2.6 Idempotency Store
- [ ] Redis-based idempotency key storage with TTL
- [ ] PostgreSQL fallback for persistence
- [ ] `execute_idempotent(key, operation)` utility

### Verification
- [ ] Policy engine correctly approves/denies all test scenarios
- [ ] Mandate verification catches all constraint violations
- [ ] Payment state machine rejects invalid transitions
- [ ] Audit chain passes integrity verification
- [ ] Idempotency store deduplicates correctly

---

## 5. Phase 3: Agents & RAG (Days 3-4)

### Goal
Working buyer and merchant agents with meaningful RAG.

### Tasks

#### 3.1 RAG Pipeline
- [ ] `rag/embeddings.py` — OpenAI text-embedding-3-small client
- [ ] `rag/query_parser.py` — LLM structured output to extract search filters
- [ ] `rag/hybrid_search.py` — Combined pgvector + tsvector + JSONB query
- [ ] Embed all seed catalog products
- [ ] Test: "mechanical keyboard for coding under 6000" returns relevant results

#### 3.2 Buyer Agent (LangGraph)
- [ ] `agents/buyer/state.py` — BuyerState TypedDict with custom reducers
- [ ] `agents/buyer/nodes.py`:
  - `intent_parsing` — LLM extracts category, budget, features
  - `discovery` — Creates DISCOVERY_REQUEST, sends via ACP
  - `retrieval` — Receives CATALOG_RESPONSE, processes results
  - `comparison` — Scores/ranks products, creates comparison matrix
  - `clarification` — Asks user follow-up questions
  - `recommendation` — Presents top choice with reasoning
  - `mandate_check` — Verifies active mandate covers purchase
  - `checkout` — `interrupt()` for human-in-the-loop payment
  - `confirmation` — Post-payment order confirmation
- [ ] `agents/buyer/graph.py` — StateGraph with conditional edges
- [ ] System prompts that constrain agent behavior

#### 3.3 Merchant Agent (LangGraph)
- [ ] `agents/merchant/state.py` — MerchantState TypedDict
- [ ] `agents/merchant/nodes.py`:
  - `catalog_query` — Search products using RAG
  - `product_response` — Format CATALOG_RESPONSE
  - `upsell_evaluation` — Find cross-sell opportunities
  - `stock_check` — Verify availability
  - `reservation` — Reserve stock (TTL)
  - `campaign_trigger` — Post-purchase campaign actions
  - `policy_check` — Campaign policy verification
- [ ] `agents/merchant/graph.py` — StateGraph

#### 3.4 ACP Protocol Router
- [ ] `protocol/router.py` — Route messages between buyer ↔ merchant
- [ ] `protocol/envelope.py` — Create/validate MessageEnvelope
- [ ] `protocol/handlers.py` — Handle each message type
- [ ] Message types: DISCOVERY_REQUEST, CATALOG_RESPONSE, CHECKOUT_INTENT, CHECKOUT_OFFER, CHECKOUT_AUTHORIZATION, UPSELL_OFFER, CAMPAIGN_ACTION

#### 3.5 Campaign Service
- [ ] `services/campaign_service.py`
- [ ] Campaign rules: post-purchase upsell, abandoned cart coupon
- [ ] Policy-bounded: frequency limits, discount caps
- [ ] Idempotent campaign actions
- [ ] Audit logging for all campaign events

### Verification
- [ ] RAG returns relevant products for natural language queries
- [ ] Buyer agent navigates full graph: intent → recommendation
- [ ] Merchant agent responds to discovery requests correctly
- [ ] ACP messages flow between agents
- [ ] Campaign service triggers post-purchase upsell

---

## 6. Phase 4: Integration (Day 5)

### Goal
Complete end-to-end flow from user message to Razorpay payment.

### Tasks

#### 4.1 FastAPI Application
- [ ] `api/main.py` — App factory with lifespan (DB pool, Redis, checkpointer)
- [ ] `api/deps.py` — Dependency injection
- [ ] `api/v1/chat.py` — SSE streaming chat endpoint
- [ ] `api/v1/checkout.py` — Payment authorization + resume endpoints
- [ ] `api/v1/mandates.py` — Mandate CRUD
- [ ] `api/v1/catalog.py` — Product search
- [ ] `api/v1/orders.py` — Order status
- [ ] `api/v1/audit.py` — Audit trail viewer
- [ ] `api/v1/webhooks.py` — Razorpay webhook receiver

#### 4.2 LangGraph Human-in-the-Loop
- [ ] Buyer graph `checkout` node uses `interrupt()` to pause for payment
- [ ] Frontend receives `PAYMENT_AUTHORIZATION_REQUIRED` event
- [ ] User completes Razorpay Checkout
- [ ] Backend receives callback, calls `Command(resume=...)` to continue graph
- [ ] Graph proceeds to `confirmation` node

#### 4.3 Webhook Integration
- [ ] Razorpay webhook handler with signature verification
- [ ] Idempotent webhook processing
- [ ] Handle: `order.paid`, `payment.captured`, `payment.failed`
- [ ] ngrok setup for local webhook testing

#### 4.4 Failure Scenario
- [ ] Simulate: payment captures but order creation fails (inject error)
- [ ] System enters `RECONCILIATION_NEEDED` state
- [ ] Retry logic attempts order creation
- [ ] If retries exhausted, initiate refund
- [ ] Full audit trail of the failure + recovery
- [ ] **This is the "one failure handled gracefully" for the buildathon**

#### 4.5 Integration Tests
- [ ] Full buyer flow: message → discovery → compare → checkout → confirm
- [ ] Mandate denial flow: exceed budget → blocked with explanation
- [ ] Failure + recovery flow: payment OK → order fails → reconciliation
- [ ] Audit trail verification for complete flow

### Verification
- [ ] Complete chat → payment → order flow works end-to-end
- [ ] Razorpay test payment completes with real API
- [ ] Failure scenario recovers gracefully
- [ ] Audit trail is complete and verifiable

---

## 7. Phase 5: Frontend (Day 6)

### Goal
Polished UI for the demo video.

### Tasks

#### 5.1 Next.js Setup
- [ ] Create Next.js 14 app in `frontend/`
- [ ] Tailwind CSS + shadcn/ui components
- [ ] SSE client for chat streaming

#### 5.2 Chat Interface
- [ ] Conversational UI (messages, typing indicator)
- [ ] Product comparison cards (inline in chat)
- [ ] Agent reasoning visible (expandable)

#### 5.3 Checkout Flow
- [ ] Mandate creation card
- [ ] Payment authorization modal
- [ ] Razorpay Checkout integration (JS SDK)
- [ ] Payment confirmation display

#### 5.4 Audit Trail Viewer
- [ ] Timeline view of all events
- [ ] Expandable event details
- [ ] Hash chain integrity indicator
- [ ] State labels: "Razorpay Test Mode", "Internal State", "Simulated"

#### 5.5 Campaign Panel
- [ ] Upsell recommendation card
- [ ] Campaign action log

### Verification
- [ ] Full demo flow works through the UI
- [ ] Audit trail displays correctly
- [ ] Razorpay Checkout popup works

---

## 8. Phase 6: Polish & Demo (Day 6.5)

### Tasks

- [ ] Record ~5 minute pitch video
- [ ] Demo script walkthrough (per DEMO_FLOW.md)
- [ ] README cleanup with screenshots
- [ ] Architecture diagram final polish
- [ ] Ensure all code is clean, documented, and committed
- [ ] Final `.env.example` verification
- [ ] Repository public-ready

---

## 9. Minimum Viable Vertical Slice

**The single path that must work for a successful demo:**

```
User says "I need a mechanical keyboard under ₹6,000"
    ↓
Buyer Agent parses intent (LangGraph: intent_parsing node)
    ↓
ACP DISCOVERY_REQUEST → Merchant Agent
    ↓
Merchant Agent searches catalog (pgvector hybrid search)
    ↓
ACP CATALOG_RESPONSE → Buyer Agent (3-5 products)
    ↓
Buyer Agent compares, recommends top pick
    ↓
User says "Buy the Keychron K2"
    ↓
Mandate check: active mandate covers ₹4,999, electronics, this merchant
    ↓
Policy check: within budget, no duplicate, rate limit OK
    ↓
LangGraph interrupt() → User sees checkout card
    ↓
Razorpay Order created (POST /v1/orders, test mode)
    ↓
User completes payment (Razorpay Checkout, test card 4111...)
    ↓
Signature verification → payment confirmed
    ↓
Internal order created, mandate updated
    ↓
LangGraph Command(resume=...) → confirmation node
    ↓
User sees: "Order confirmed! ✅"
    ↓
Audit trail: 12+ events, hash-chained, verifiable
    ↓
Merchant triggers upsell: "Want a wrist rest?"
    ↓
BONUS: Failure demo → payment OK, order fails → reconciliation → refund
```

### Minimum Components for This Slice

| Component | Required | Skippable |
|-----------|----------|-----------|
| Product catalog (10+ items, pgvector) | ✅ | |
| Buyer Agent LangGraph (all nodes) | ✅ | |
| Merchant Agent LangGraph (catalog + checkout) | ✅ | |
| ACP message routing | ✅ | |
| Mandate service | ✅ | |
| Policy engine (budget, mandate, duplicate) | ✅ | |
| Payment service + state machine | ✅ | |
| Razorpay adapter (orders, verification) | ✅ | |
| Audit engine (hash chain) | ✅ | |
| Order service | ✅ | |
| Campaign service (post-purchase upsell) | ✅ | |
| Failure scenario (reconciliation) | ✅ | |
| Chat UI (SSE streaming) | ✅ | |
| Razorpay Checkout integration | ✅ | |
| Audit trail viewer | ✅ | |
| Multi-merchant support | | ✅ Skip |
| Full campaign orchestrator | | 🟡 Minimal |
| User authentication | | ✅ Skip (session) |
| Production error handling | | ✅ Skip |
| Comprehensive fulfilment | | ✅ Skip (simulate) |

---

## 10. Risks & Assumptions

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| LangGraph complexity slows development | High | Start with simple graph, add nodes incrementally |
| Razorpay webhook delivery to localhost | Medium | Use ngrok; fallback to polling `GET /v1/orders/{id}` |
| LLM inconsistency in intent parsing | Medium | Constrain with structured output; fallback prompts |
| pgvector embedding quality for product search | Medium | Use hybrid search (vector + FTS + SQL filters) |
| Time pressure (6 days to Sept 5) | High | Strict vertical slice; cut scope ruthlessly |
| Razorpay test mode limitations | Low | Well-documented, widely used |

### Assumptions

| Assumption | Needs Verification |
|-----------|-------------------|
| Razorpay test account creation is instant | ✅ Verify during Phase 1 |
| OpenAI API for embeddings is available and affordable | ✅ Verify; fallback to Cohere/local |
| LangGraph `interrupt()` + `Command(resume=...)` works with FastAPI SSE | ✅ Verify in Phase 4 integration |
| pgvector HNSW index performs well at 10-50 products | ✅ Should be fine at demo scale |
| Razorpay Checkout JS works in a Next.js SSR context | ✅ Verify; may need client-side only |
| ngrok free tier is sufficient for webhook testing | ✅ Verify; paid tier if needed |

### Things That Need Verification Before Implementation

1. **Razorpay Test Mode API key generation** — Sign up, generate keys, confirm test order works
2. **LangGraph interrupt + resume with AsyncPostgresSaver** — Build minimal proof-of-concept
3. **pgvector hybrid search query** — Test the combined vector + FTS + JSONB SQL query
4. **Razorpay Checkout + Next.js** — Confirm Checkout JS SDK works in our frontend setup
5. **SSE streaming from LangGraph through FastAPI** — Verify token-by-token streaming works
6. **Razorpay webhook + ngrok** — Set up and confirm webhook delivery

---

## 11. Definition of Done (Demo-Ready)

- [ ] User can have a natural conversation about products
- [ ] Products are retrieved from a real catalog with vector search
- [ ] Agent compares products and recommends with reasoning
- [ ] Mandate bounds are enforced (denial shown for over-budget)
- [ ] Real Razorpay test payment completes end-to-end
- [ ] Signature verification confirms payment authenticity
- [ ] Audit trail shows 10+ events with hash chain integrity
- [ ] One failure scenario handled gracefully (payment OK, order fails)
- [ ] Post-purchase upsell campaign triggers
- [ ] 5-minute video demonstrates all of the above
- [ ] README documents architecture and setup
- [ ] Code is clean, modular, and honestly labeled
