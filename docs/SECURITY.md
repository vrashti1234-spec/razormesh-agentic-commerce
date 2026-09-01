# RazorMesh Security Architecture

This document defines the security architecture and boundaries for **RazorMesh** — an agentic commerce prototype developed for the Razorpay AI Buildathon. 

**CORE PRINCIPLE:**
> LLM proposes → Policy engine validates → Deterministic code executes → Payment provider confirms.
> 
> **Never:** LLM → Razorpay directly.

---

## 1. Security Architecture Overview

The RazorMesh security model relies on strict separation of concerns, isolating non-deterministic AI agents from deterministic execution environments and payment infrastructure. The architecture is divided into three distinct zones.

```mermaid
flowchart TD
    subgraph "AI Zone (Untrusted)"
        A1[Buyer Agent\nLLM] 
        A2[Merchant Agent\nLLM]
    end

    subgraph "Trust Boundary (RazorMesh Layer)"
        PE[Policy Engine\n(Deterministic)]
        M[Mandate Validator]
    end

    subgraph "Execution Zone (Deterministic)"
        PS[Payment Service]
        AT[Audit Trail]
    end
    
    RP[Razorpay API]

    A1 -- Proposes PaymentIntent --> PE
    A2 -- Proposes Campaign/Action --> PE
    
    PE -- Validates against Policies --> M
    M -- Checks Mandate Constraints --> PS
    
    PS -- Executes with Credentials --> RP
    RP -- Confirms/Fails --> PS
    
    PE -. Logs Decision .-> AT
    PS -. Logs Outcome .-> AT
```

- **AI Zone (Untrusted)**: Where the LLM operates. Inputs and outputs here are considered non-deterministic and potentially adversarial. The LLM is an untrusted input source.
- **Trust Boundary (RazorMesh Layer)**: Where the policy engine and mandate validators sit. This layer strictly evaluates structured proposals from the AI Zone using deterministic code.
- **Execution Zone (Deterministic)**: Where approved actions are executed (e.g., calling Razorpay APIs) and recorded securely.

---

## 2. Trust Boundary: The RazorMesh Layer

The RazorMesh trust boundary acts as an impenetrable wall between the AI agents and payment/order execution.

- **Proposals, Not Commands**: All outputs from AI agents are treated exclusively as **PROPOSALS** (e.g., a `PaymentIntent`), not direct commands.
- **Deterministic Validation**: Every proposal must pass through deterministic policy validation. The Policy Engine is pure, strictly typed code.
- **No LLM in Validation**: Under no circumstances is an LLM used in the validation, approval, or execution path. 

---

## 3. Payment Security

### 3.1 Credential Isolation
- **Storage**: Razorpay API keys and secrets are stored strictly in environment variables.
- **Context Exclusion**: Credentials are never passed to the LLM context, prompt, or system instructions.
- **No Logging**: Credentials are never logged or exposed in traces.
- **Agent State**: Agent memory and state objects are stripped of any payment credentials. The LLM has **NO access** to payment credentials.

### 3.2 Payment Flow Security
1. **Generation**: The LLM generates a structured JSON `PaymentIntent` based on the user's goal. It does not generate raw API calls.
2. **Validation**: The `PaymentIntent` is validated against the active user mandate.
3. **Constraint Checking**: Constraints including amount limits, approved merchants, product categories, expiry date, and currency are strictly checked.
4. **Idempotency**: An idempotency key is generated deterministically before execution.
5. **Execution**: A deterministic `PaymentService` (not the LLM) executes the payment via the Razorpay API using secure credentials.
6. **Verification**: Razorpay's webhook response is verified using signature checks (HMAC-SHA256) to ensure authenticity.
7. **Audit**: The entire flow, result, and state transition are logged to the immutable audit trail.

### 3.3 Mandate Model Security
- **Human Created**: Mandates (budget and rules) are created explicitly by the user (human), never by the LLM.
- **Immutability**: Once created, mandates are immutable. Any changes require creating a new mandate with explicit user approval.
- **Expiry**: All mandates have a strict expiry timestamp.
- **Bounds**: Mandates possess maximum amount bounds (per transaction and aggregate).
- **Scope**: Mandates are cryptographically or logically scoped to specific merchants, product categories, or campaign tags.
- **Verification**: Mandate verification is purely deterministic code.

---

## 4. Agent Security

### 4.1 Buyer Agent Constraints
- **No Execution Rights**: Cannot execute payments directly.
- **No Credential Access**: Cannot access API keys or payment credentials.
- **Propose Only**: Can only PROPOSE purchases strictly within the bounds of a predefined mandate.
- **Read-Only Mandates**: Cannot create, modify, or delete mandates.
- **Full Transparency**: All proposals and intermediate chain-of-thought outputs are logged.

### 4.2 Merchant Agent Constraints
- **No Buyer Data Access**: Cannot access buyer payment methods, balances, or private PII.
- **No Charge Initiation**: Cannot initiate arbitrary charges against buyers.
- **Protocol Only**: Can only respond to standardized RazorMesh protocol messages.
- **Bounded Campaigns**: Campaign actions and targeted promotions are bounded by strict policies.
- **Frequency Limits**: Rate limiting and campaign frequency caps are enforced to prevent spam or aggressive negotiation loops.

---

## 5. Policy Engine

The Policy Engine is the core decision-maker for all agent proposals. It uses pure deterministic rule evaluation (no LLM).

- **Rule Definition**: Rules are defined strictly in code or structured configuration (JSON/YAML).
- **Rule Categories**:
  - **Budget Limits**: Per-transaction caps, daily/weekly aggregate limits.
  - **Merchant Control**: Allowlist/blocklist of approved merchants.
  - **Product Restrictions**: Restrictions on specific categories (e.g., no alcohol/tobacco).
  - **Quantity Limits**: Caps on the number of items per order.
  - **Time-Based**: Trading hours, mandate expiry deadlines.
  - **Duplicates**: Detection of duplicate or highly similar requests.
  - **Rate Limiting**: Throttling agent proposals to prevent looping.
- **Evaluation Outcomes**: The engine evaluates proposals and returns:
  - `APPROVED`: Execution may proceed.
  - `DENIED`: Execution blocked, with a deterministic reason provided back to the agent.
  - `REQUIRES_ESCALATION`: Execution blocked pending explicit human-in-the-loop approval.
- **Audit Logging**: All policy decisions (inputs, rules triggered, outcomes) are logged to the audit trail.

---

## 6. Idempotency & Replay Protection

To ensure payments and state changes happen exactly once despite retries, network failures, or agent loops:
- **Unique Keys**: Every money-changing or state-mutating operation requires a unique idempotency key.
- **Structure**: Idempotency keys follow the structure: `{operation_type}:{entity_id}:{sequence}` (e.g., `payment:ord_12345:req_1`).
- **State Machine**: A strict finite state machine prevents invalid transitions (e.g., charging a `PAID` order).
- **Webhook Deduplication**: Webhooks are checked against existing processed events to detect duplicates.
- **At-Least-Once Delivery**: Handlers are designed to be idempotent, ensuring safe retries.

---

## 7. Audit Trail Security

Accountability is maintained through a secure audit log.

- **Immutable Append-Only**: All events are appended to an immutable audit log.
- **Event Scope**: Logged events include agent proposals, policy engine decisions, payment attempts, Razorpay responses, and state transitions.
- **Data Structure**: Each event contains: `event_id`, `timestamp`, `actor`, `action`, `input`, `output`, and `decision`.
- **Tamper Evidence**: Implemented via **Hash Chaining**. Each event includes the cryptographic hash of the previous event (e.g., `hash_n = SHA256(event_n + hash_n-1)`).
- **Not Blockchain**: This is a simple, lightweight hash chain for internal verifiability, avoiding the overhead of a distributed ledger while ensuring records haven't been retroactively altered.

---

## 8. Data Classification

| Data Type | Example | Sensitivity | LLM Access | Logging |
|---|---|---|---|---|
| **Payment Credentials** | Razorpay Secret Key | Critical | **NO** | Never |
| **Financial Auth** | Credit Card Info / Tokens | High | **NO** | Never (handled by Razorpay) |
| **PII** | User Email, Physical Address | High | Yes (Masked where possible) | Redacted before logging |
| **Mandates** | Budget: $50 for Groceries | Medium | Yes (Read-only) | Full Logging |
| **Order Metadata** | Product Name, Quantity, Price | Low | Yes (Full access) | Full Logging |
| **Agent CoT** | Intermediate reasoning steps | Low | Yes (Generator) | Full Logging |

---

## 9. Prototype vs Production Security

This table honestly reflects the security posture of the RazorMesh AI Buildathon prototype compared to a production-ready system.

| Security Measure | Status in Prototype | Production Implementation |
|---|---|---|
| **Hash-chain Audit** | **Implemented** | Distributed immutable ledger (e.g., QLDB) |
| **Razorpay Signature Verification** | **Implemented** (Test Mode) | Implemented (Live Mode) |
| **Credential Isolation** | **Implemented** (.env) | Secrets Manager (e.g., AWS Secrets Manager) |
| **Mandate Bounds Checking** | **Implemented** | Implemented with distributed locking |
| **mTLS between microservices** | **Deferred** | Fully Implemented (Service Mesh) |
| **User Authentication** | **Simplified** (Session-based, mocked) | OAuth 2.0 / OIDC / MFA |
| **Mandate Cryptographic Signatures** | **Simulated** (HMAC) | Asymmetric keys (RSA/ECDSA) signed by user device enclaves |
| **PII Redaction in Logs** | **Simulated** (Basic Regex) | Advanced DLP and tokenization pipelines |

---

## 10. Threat Model

| Threat | Description | Mitigation Strategy |
|---|---|---|
| **LLM Prompt Injection** | Adversary injects prompts to make the agent buy unauthorized goods. | **Policy engine** intercepts all proposals. Deterministic constraints prevent unauthorized actions regardless of agent intent. |
| **Replay Attacks** | Replaying a valid payment request multiple times to drain funds. | **Idempotency keys** and strict state machine transitions block duplicate operations. |
| **Credential Leakage** | Agent accidentally reveals API keys in chat or logs. | **Credential isolation**. Keys are never passed to the LLM context or memory. |
| **Unauthorized Purchases** | Agent hallucinates a purchase without user consent. | **Mandate bounds** dictate strict limits. Operations outside bounds require explicit **human approval**. |
| **Agent Impersonation** | Malicious actor spoofing agent identities to bypass limits. | Cryptographic or robust **Agent ID validation** at the protocol boundary. |
| **Data Exfiltration** | Agent leaks user PII to external untrusted endpoints. | **Data classification**, strict egress network policies, and PII redaction before logging. |

---

*Document generated for the Razorpay AI Buildathon.*
