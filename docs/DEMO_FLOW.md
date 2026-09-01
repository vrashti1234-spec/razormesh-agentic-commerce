# RazorMesh: End-to-End Demonstration Flow

This document defines the end-to-end demonstration flow for RazorMesh, built for the **Razorpay AI Buildathon 2026** (Track: AI Growth & Agentic Commerce). It outlines the core scenarios that showcase working product functionality, explainable/bounded money actions, complete auditability, and graceful failure handling using Razorpay Test Mode.

---

## 1. Demo Scenario

**The Setting:**
We demonstrate the complete lifecycle of an agentic commerce transaction.

**The Persona:**
- **User:** Priya, a software developer looking to upgrade her workstation.
- **Goal:** She needs a mechanical keyboard suitable for coding, within a specific budget.

**The Interaction:**
Priya interacts conversationally with her personal **Buyer Agent**, which negotiates on her behalf with the **Merchant Agent** via the Agentic Commerce Protocol (ACP). The system will demonstrate discovery, negotiation, authorized checkout, and post-purchase upselling, all backed by a verifiable audit trail.

---

## 2. Vertical Slice: The Happy Path

This step-by-step walkthrough represents the core functional loop of RazorMesh:

1. **User Intent:** Priya says, *"I need a good mechanical keyboard for coding, under ₹6,000."*
2. **Intent Parsing:** The Buyer Agent interprets the request (Category: Mechanical Keyboard, Budget: ≤600,000 paise, Use Case: Coding).
3. **Protocol Initiation:** Buyer Agent sends a `DISCOVERY_REQUEST` to the Merchant Agent via ACP.
4. **Catalog Retrieval:** Merchant Agent queries its catalog using vector search (RAG) and returns 3-5 matching keyboards.
5. **Evaluation:** Buyer Agent analyzes the options based on Priya's preferences (switch type, connectivity, build quality, price).
6. **Recommendation:** Buyer Agent presents a comparison summary to Priya, highlighting the best match.
7. **Selection:** Priya says, *"Get me the Keychron one."*
8. **Mandate Verification:** The system checks Priya's active mandates. She has a valid mandate: `[Category: Electronics, Max Amount: ₹8,000]`.
9. **Checkout Intent:** Buyer Agent sends a `CHECKOUT_INTENT` to the Merchant Agent.
10. **Offer Creation:** Merchant Agent confirms stock availability, reserves the item, and responds with a `CHECKOUT_OFFER`.
11. **Human-in-the-Loop:** Priya reviews the offer and authorizes the purchase.
12. **Order Generation:** The payment service generates a Razorpay Order ID (Test Mode).
13. **Payment Execution:** The Razorpay checkout modal opens; Priya completes the transaction using a test card or test UPI ID.
14. **Verification:** The system verifies the Razorpay payment signature.
15. **Confirmation:** The order is confirmed, and simulated fulfillment is initiated.
16. **Transparency:** The full transaction lifecycle is appended to the user-facing audit trail.

---

## 3. The Upsell Flow

Demonstrating AI-driven growth post-checkout:

1. **Trigger:** Upon successful checkout, the Merchant Agent's Campaign Orchestrator triggers a rule: *"Customers who bought this keyboard also bought a wrist rest."*
2. **Proposition:** The Buyer Agent receives the upsell offer and presents it to Priya conversationally.
3. **Decision:** Priya can accept or dismiss the offer with a single click/tap.
4. **Frictionless Checkout:** If accepted, the flow re-uses the active session and mandate constraints to process the upsell quickly.
5. **Auditing:** The campaign action and subsequent decision are securely logged in the audit trail.

---

## 4. The Failure Scenario (Required by Buildathon)

Demonstrating system resilience and graceful degradation:

1. **Simulated Failure:** The payment succeeds on Razorpay, but the internal order creation fails (intentionally simulated via a mock error).
2. **Detection:** The RazorMesh reconciliation engine detects the inconsistency between the payment status and the order state.
3. **State Transition:** The system enters a `RECONCILIATION` state.
4. **Logging:** The failure, along with full context, is logged immutably.
5. **Recovery:** The system automatically queues a retry for order creation.
6. **User Communication:** Priya's UI updates to explicitly state: *"Payment received, order being processed. Experiencing slight delays."* (No silent failures).
7. **Audit Visibility:** The exact point of failure and the automated recovery attempts are visible in the technical audit trail.

---

## 5. Mandate Demo

Showcasing bounded, explainable money actions:

1. **Creation:** Priya creates a new mandate setting: *"Allow purchases from electronics merchants up to ₹8,000 for the next 7 days."*
2. **Execution:** The system translates this into a deterministic, bounded policy rule.
3. **Violation Attempt:** Priya attempts to purchase a monitor worth ₹12,000.
4. **Rejection:** The policy engine checks the mandate and immediately **FAILS** the transaction before it reaches the payment gateway.
5. **Explanation:** The audit trail and UI clearly show the denial reason: *"Transaction exceeds active mandate limit of ₹8,000."*

---

## 6. Audit Trail Demo

Highlighting explainability and trust:

- **End-to-End Visibility:** The interface displays every state change from the initial intent to payment and simulated fulfillment.
- **Data Points Shown:**
  - What the user requested.
  - What the agent proposed.
  - Which policy/mandate was evaluated.
  - What payment action occurred.
- **Integrity Verification:** A demonstration of the hash-chained events, proving the sequence of actions has not been tampered with.
- **Clarity:** Clear differentiation between Razorpay API responses, internal database state, and LLM-driven agent decisions.

---

## 7. UI Screens to Demonstrate

1. **Chat Interface:** The primary conversational surface for the Buyer Agent.
2. **Product Comparison Card:** A structured, dynamic UI element presenting the agent's evaluation.
3. **Mandate Management:** A dashboard to view, create, and revoke spending mandates.
4. **Checkout Authorization Modal:** The Human-in-the-Loop gatekeeper screen.
5. **Razorpay Checkout:** The standard Test Mode payment popup.
6. **Order Confirmation:** Post-purchase success state.
7. **Campaign Activity Panel:** Showing proactive upsell prompts.
8. **Audit Trail Timeline:** A chronologically ordered, hash-linked log of system events.
9. **System Status/Recovery:** Explicit messaging for failure handling.

---

## 8. What is Real vs Simulated

*RazorMesh maintains strict honesty about its technical boundaries for the Buildathon.*

| Feature | Status |
|---------|--------|
| Conversational AI (LLM) | **Real** (Gemini/GPT integration) |
| Product catalog + RAG | **Real** (pgvector based search) |
| Agent-to-agent protocol | **Real** (Our custom ACP prototype) |
| Razorpay payments | **Real** (Test Mode API) |
| Payment signature verification | **Real** |
| Mandate authorization | **Real** (Our deterministic implementation) |
| Policy engine | **Real** (Code-based rule evaluation) |
| Audit trail | **Real** (Hash-chained event logs) |
| Fulfillment | *Simulated* (State transitions only) |
| Shipping/delivery | *Simulated* |
| User authentication | *Simplified* (Session-based for demo) |
| Campaign orchestrator | **Real** (Rule-based triggers) |
| Multi-merchant support | *Single merchant* (Scoped for demo) |

---

## 9. Pitch Video Outline (~5 Minutes)

- **0:00 - 0:30 | The Problem:** AI agents need trusted, bounded, and auditable payment infrastructure to participate in real-world commerce.
- **0:30 - 1:30 | Architecture:** Brief overview of the Trust Boundary, ACP, and how Razorpay fits into the agentic ecosystem.
- **1:30 - 3:30 | Live Demo:** Walkthrough of the Happy Path (Discovery to Purchase) + The Failure Scenario (Graceful recovery).
- **3:30 - 4:30 | Technical Deep-Dive:** Showcasing the deterministic Mandate Model, the Policy Engine, and the immutable Audit Trail.
- **4:30 - 5:00 | Conclusion:** The path to production and how this redefines merchant growth.

---

## 10. Minimum Viable Demo Checklist

**Must-Haves before September 5:**
- [ ] Working LLM integration for intent parsing.
- [ ] Basic vector database populated with mock products.
- [ ] Agentic Commerce Protocol (ACP) mock routing (Buyer ↔ Merchant).
- [ ] Deterministic Policy Engine for Mandate limits.
- [ ] Razorpay Test Mode integration (Orders API + Checkout UI).
- [ ] Payment signature verification webhook/endpoint.
- [ ] Hash-chained audit logging mechanism.
- [ ] UI capable of rendering the chat, the authorization modal, and the audit timeline.
- [ ] Configured simulated failure path for reconciliation demo.
