from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.agents.buyer_agent import buyer_agent
from app.agents.merchant_agent import search_catalog
from app.services.product_search_service import search_products
from app.protocols.acp import create_checkout_session
from app.protocols.ap2 import (
    verify_checkout_mandate,
    verify_payment_mandate,
)
from app.services.policy_engine import evaluate_payment_policy
from app.services.razorpay_services import (
    RazorpayOrderRequest,
    get_razorpay_service,
)
from app.services.audit_service import (
    get_audit_log,
    record_audit_event,
)
from app.services.fulfillment_service import fulfill_order

from uuid import uuid4
import re


app = FastAPI(title="RazorMesh")


# -------------------------------------------------
# SERVER-SIDE STATE
# -------------------------------------------------

# Server-side record of Razorpay orders created by RazorMesh.
server_orders = {}

# Payments that have already been successfully processed.
processed_payments = {}

# Conversation state for the conversational Buyer Agent.
conversations = {}


# -------------------------------------------------
# FRONTEND
# -------------------------------------------------

app.mount(
    "/frontend",
    StaticFiles(directory="app/frontend"),
    name="frontend",
)


# -------------------------------------------------
# BASIC ENDPOINTS
# -------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/audit")
def audit(transaction_id: str | None = None):
    return {
        "transaction_id": transaction_id,
        "events": get_audit_log(transaction_id),
    }


@app.get("/config/public")
def public_config():
    settings = get_settings()

    return {
        "razorpay_key_id": settings.razorpay_key_id
    }


# -------------------------------------------------
# BUYER CONVERSATION HELPERS
# -------------------------------------------------

def _is_explicit_approval(message: str) -> bool:
    """
    Deterministic approval gate.

    The LLM is NOT allowed to decide whether the user
    approved the purchase.
    """

    normalized = message.strip().lower()

    approval_phrases = {
        "yes",
        "yes buy",
        "yes, buy",
        "buy",
        "purchase",
        "proceed",
        "go ahead",
        "confirm",
        "confirm purchase",
        "place order",
        "place the order",
        "buy it",
        "purchase it",
    }

    return normalized in approval_phrases


def _extract_budget(constraints: list[str]) -> float | None:
    """
    Extract a simple INR budget from the Buyer's constraints.

    Examples:
    - under ₹10k
    - below 10000
    - maximum ₹15000
    """

    for constraint in constraints:
        text = constraint.lower().replace(",", "")

        match = re.search(
            r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(k|thousand)?",
            text,
        )

        if not match:
            continue

        value = float(match.group(1))
        multiplier = match.group(2)

        if multiplier in {"k", "thousand"}:
            value *= 1000

        if any(
            word in text
            for word in [
                "under",
                "below",
                "maximum",
                "max",
                "less",
            ]
        ):
            return value

    return None


def _build_recommendation(
    buyer_result: dict,
) -> dict:
    """
    Discover real products from the live web using the Buyer's
    extracted product query.

    The Buyer Agent understands the user's request.
    The product search service discovers real online options.
    No product is hardcoded into this recommendation layer.
    """

    product_query = buyer_result.get("product_query", "").strip()
    quantity = int(buyer_result.get("quantity", 1) or 1)

    if not product_query:
        return {
            "found": False,
            "message": (
                "I couldn't identify what product you want to buy."
            ),
            "options": [],
        }

    results = search_products(
        product_query,
        max_results=5,
    )

    if not results:
        return {
            "found": False,
            "message": "I couldn't find matching products online.",
            "options": [],
        }

    options = []

    for result in results:
        options.append({
            "name": result.title,
            "url": result.url,
            "snippet": result.snippet,
            "source": result.source,
        })

    return {
        "found": True,
        "product_query": product_query,
        "quantity": quantity,
        "options": options,
    }


# -------------------------------------------------
# CONVERSATIONAL BUYER AGENT
# -------------------------------------------------

@app.post("/agent/chat")
def agent_chat(request: dict):
    """
    Conversational Buyer Agent entry point.

    First message:
        Understand request
        -> recommendation
        -> ask for approval

    Approval message:
        Deterministically verify approval
        -> invoke existing purchase pipeline

    The purchase pipeline is NEVER started without
    explicit user approval.
    """

    conversation_id = request.get("conversation_id")
    message = request.get("message", "").strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="message is required",
        )

    # Create a new conversation if necessary.
    if not conversation_id:
        conversation_id = f"conv_{uuid4().hex[:12]}"

    conversation = conversations.get(conversation_id)

    # =================================================
    # FIRST MESSAGE
    # =================================================

    if conversation is None:

        buyer_state = {
            "customer_request": message,
            "product_query": "",
            "selected_product": "",
            "quantity": 1,
            "preferences": [],
            "constraints": [],
        }

        # Buyer Agent understands the user's natural-language request.
        buyer_result = buyer_agent(buyer_state)

        # Deterministically match the extracted intent
        # against the canonical merchant catalog.
        recommendation = _build_recommendation(
            buyer_result
        )

        if not recommendation["found"]:
            return {
                "conversation_id": conversation_id,
                "status": "no_match",
                "buyer": buyer_result,
                "recommendation": recommendation,
                "message": recommendation["message"],
            }

        # Store conversation state.
        conversations[conversation_id] = {
            "customer_request": message,
            "buyer_result": buyer_result,
            "recommendation": recommendation,
            "status": "awaiting_approval",
        }

        return {
            "conversation_id": conversation_id,
            "status": "awaiting_approval",
            "buyer": buyer_result,
            "recommendation": recommendation,
            "message": (
                f"I found {len(recommendation['options'])} "
                f"online option(s) for "
                f"{buyer_result['product_query']}. "
                f"Please choose an option and then confirm "
                f"that you want to buy it."
            ),
        }

    # =================================================
    # EXISTING CONVERSATION
    # =================================================

    if conversation["status"] != "awaiting_approval":
        return {
            "conversation_id": conversation_id,
            "status": conversation["status"],
            "message": (
                "This conversation has already been completed."
            ),
        }

    # =================================================
    # DETERMINISTIC APPROVAL GATE
    # =================================================

    if not _is_explicit_approval(message):

        # Explicit cancellation.
        if message.lower() in {
            "no",
            "cancel",
            "stop",
            "don't buy",
            "do not buy",
        }:
            conversation["status"] = "cancelled"

            return {
                "conversation_id": conversation_id,
                "status": "cancelled",
                "message": (
                    "Purchase cancelled. "
                    "No payment flow was started."
                ),
            }

        # Ambiguous response.
        return {
            "conversation_id": conversation_id,
            "status": "awaiting_approval",
            "message": (
                "I need an explicit confirmation before "
                "starting the purchase. Please reply with "
                "'yes', 'buy', or 'proceed'."
            ),
        }

    # =================================================
    # USER APPROVED
    # =================================================

    conversation["status"] = "approved"

    # Invoke the EXISTING purchase pipeline.
    #
    # This is the important boundary:
    # the purchase flow cannot be reached from the
    # conversational endpoint until explicit approval
    # has been deterministically detected.
    purchase_result = agent_purchase(
        {
            "customer_request": conversation["customer_request"],
            "approval_confirmed": True,
        }
    )

    conversation["status"] = "purchase_started"

    return {
        "conversation_id": conversation_id,
        "status": "purchase_started",
        "message": (
            "Approved. I've passed the purchase through "
            "the merchant, authorization, trust-policy, "
            "and Razorpay flow."
        ),
        "purchase": purchase_result,
    }


# -------------------------------------------------
# EXISTING AGENT PURCHASE PIPELINE
# -------------------------------------------------

@app.post("/agent/purchase")
def agent_purchase(request: dict):

    transaction_id = str(uuid4())

    # -------------------------------------------------
    # USER APPROVAL AUDIT
    # -------------------------------------------------

    if request.get("approval_confirmed") is True:
        record_audit_event(
            transaction_id=transaction_id,
            event_type="user_approval",
            status="approved",
            details={
                "source": "conversational_buyer_agent",
            },
        )

    # -------------------------------------------------
    # 1. BUYER AGENT
    # -------------------------------------------------

    buyer_state = {
        "customer_request": request["customer_request"],
        "product_query": "",
        "selected_product": "",
        "quantity": 1,
        "preferences": [],
        "constraints": [],
    }

    buyer_result = buyer_agent(buyer_state)

    record_audit_event(
        transaction_id=transaction_id,
        event_type="buyer_agent_decision",
        status="completed",
        details={
            "product_query": buyer_result["product_query"],
            "quantity": buyer_result["quantity"],
        },
    )

    # -------------------------------------------------
    # 2. ACP-STYLE CHECKOUT
    # -------------------------------------------------

    checkout = create_checkout_session(
        product_query=buyer_result["product_query"],
        quantity=buyer_result["quantity"],
        customer_request=buyer_result["customer_request"],
    )

    record_audit_event(
        transaction_id=transaction_id,
        event_type="merchant_checkout",
        status=checkout["status"],
        details={
            "checkout_id": checkout["checkout_session_id"],
        },
    )

    if checkout["status"] != "authorized":
        return {
            "status": "blocked",
            "reason": (
                "Merchant could not create "
                "an authorized checkout"
            ),
            "buyer": buyer_result,
            "acp_checkout": checkout,
        }

    mandate = checkout["mandate"]
    cart = checkout["cart"]
    item = cart.items[0]

    # -------------------------------------------------
    # 3. AP2 CHECKOUT MANDATE VERIFICATION
    # -------------------------------------------------

    mandate_valid, mandate_reason = verify_checkout_mandate(
        mandate,
        merchant_id="razormesh_demo_merchant",
        product_id=item.product_id,
        quantity=item.quantity,
        amount_paise=int(round(cart.total * 100)),
        currency=cart.currency,
        checkout_id=checkout["checkout_session_id"],
    )

    record_audit_event(
        transaction_id=transaction_id,
        event_type="checkout_mandate_verification",
        status=(
            "verified"
            if mandate_valid
            else "rejected"
        ),
        details={
            "checkout_id": checkout["checkout_session_id"],
            "reason": mandate_reason,
        },
    )

    if not mandate_valid:
        return {
            "status": "blocked",
            "reason": mandate_reason,
            "buyer": buyer_result,
            "acp_checkout": checkout,
        }

    # -------------------------------------------------
    # 4. PAYMENT MANDATE VERIFICATION
    # -------------------------------------------------

    payment_mandate = checkout["payment_mandate"]

    payment_valid, payment_reason = verify_payment_mandate(
        payment_mandate,
        merchant_id="razormesh_demo_merchant",
        checkout_id=checkout["checkout_session_id"],
        checkout_hash=mandate.checkout_hash,
        amount_paise=mandate.amount_paise,
        currency=mandate.currency,
    )

    record_audit_event(
        transaction_id=transaction_id,
        event_type="payment_mandate_verification",
        status=(
            "verified"
            if payment_valid
            else "rejected"
        ),
        details={
            "checkout_id": checkout["checkout_session_id"],
            "reason": payment_reason,
        },
    )

    if not payment_valid:
        return {
            "status": "blocked",
            "reason": payment_reason,
            "buyer": buyer_result,
            "acp_checkout": checkout,
        }

    # -------------------------------------------------
    # 5. DETERMINISTIC TRUST BOUNDARY / POLICY
    # -------------------------------------------------

    policy = evaluate_payment_policy(
        mandate,
        merchant_id="razormesh_demo_merchant",
        product_id=item.product_id,
        quantity=item.quantity,
        amount_paise=int(round(cart.total * 100)),
        currency=cart.currency,
    )

    record_audit_event(
        transaction_id=transaction_id,
        event_type="payment_policy",
        status=(
            "allowed"
            if policy.allowed
            else "blocked"
        ),
        details={
            "reason": policy.reason,
            "product_id": item.product_id,
            "quantity": item.quantity,
            "amount_paise": int(round(cart.total * 100)),
            "currency": cart.currency,
        },
    )

    if not policy.allowed:
        return {
            "status": "blocked",
            "reason": policy.reason,
            "buyer": buyer_result,
            "acp_checkout": checkout,
            "policy": policy.to_dict(),
        }

    # -------------------------------------------------
    # 6. RAZORPAY TEST MODE ORDER
    # -------------------------------------------------

    razorpay = get_razorpay_service()

    order = razorpay.create_order(
        RazorpayOrderRequest(
            amount_paise=mandate.amount_paise,
            receipt=checkout["checkout_session_id"],
            currency=mandate.currency,
            notes={
                "product_id": mandate.product_id,
                "quantity": str(mandate.quantity),
                "source": "razormesh",
            },
        )
    )

    # Store the expected order details on the server.
    server_orders[order.order_id] = {
        "checkout_id": checkout["checkout_session_id"],
        "transaction_id": transaction_id,
        "product_id": mandate.product_id,
        "quantity": mandate.quantity,
        "amount_paise": mandate.amount_paise,
        "currency": mandate.currency,
    }

    record_audit_event(
        transaction_id=transaction_id,
        event_type="razorpay_order_created",
        status="created",
        details={
            "order_id": order.order_id,
            "amount_paise": order.amount_paise,
            "currency": order.currency,
        },
    )

    return {
        "status": "order_created",
        "transaction_id": transaction_id,
        "buyer": buyer_result,
        "acp_checkout": checkout,
        "checkout_mandate": {
            "verified": True,
            "reason": mandate_reason,
        },
        "payment_mandate": {
            "verified": True,
            "reason": payment_reason,
        },
        "policy": policy.to_dict(),
        "razorpay_order": {
            "order_id": order.order_id,
            "amount_paise": order.amount_paise,
            "currency": order.currency,
            "status": order.status,
        },
    }


# -------------------------------------------------
# PAYMENT VERIFICATION
# -------------------------------------------------

@app.post("/payment/verify")
def verify_payment(request: dict):

    razorpay_order_id = request["razorpay_order_id"]
    razorpay_payment_id = request["razorpay_payment_id"]
    razorpay_signature = request["razorpay_signature"]

    # -------------------------------------------------
    # PREVENT DUPLICATE PAYMENT PROCESSING
    # -------------------------------------------------

    if razorpay_payment_id in processed_payments:
        return {
            "status": "already_processed",
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "fulfillment": processed_payments[
                razorpay_payment_id
            ],
        }

    # -------------------------------------------------
    # 1. CHECK SERVER-CREATED ORDER
    # -------------------------------------------------

    expected_order = server_orders.get(
        razorpay_order_id
    )

    if expected_order is None:
        raise HTTPException(
            status_code=400,
            detail="Unknown Razorpay order.",
        )

    transaction_id = expected_order["transaction_id"]

    razorpay = get_razorpay_service()

    # -------------------------------------------------
    # 2. VERIFY PAYMENT SIGNATURE
    # -------------------------------------------------

    verified = razorpay.verify_payment_signature(
        order_id=razorpay_order_id,
        payment_id=razorpay_payment_id,
        signature=razorpay_signature,
    )

    if not verified:
        raise HTTPException(
            status_code=400,
            detail="Invalid payment signature",
        )

    # -------------------------------------------------
    # 3. FETCH ACTUAL PAYMENT FROM RAZORPAY
    # -------------------------------------------------

    try:
        payment = razorpay.fetch_payment(
            razorpay_payment_id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch payment: {exc}",
        )

    # -------------------------------------------------
    # 4. VERIFY PAYMENT BELONGS TO OUR ORDER
    # -------------------------------------------------

    if payment.order_id != razorpay_order_id:
        raise HTTPException(
            status_code=400,
            detail="Payment does not belong to this order.",
        )

    # -------------------------------------------------
    # 5. VERIFY PAYMENT AMOUNT
    # -------------------------------------------------

    if (
        payment.amount_paise
        != expected_order["amount_paise"]
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Payment amount does not match "
                "the authorized amount."
            ),
        )

    # -------------------------------------------------
    # 6. VERIFY PAYMENT CURRENCY
    # -------------------------------------------------

    if payment.currency != expected_order["currency"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Payment currency does not match "
                "the authorized currency."
            ),
        )

    # -------------------------------------------------
    # 7. VERIFY PAYMENT STATUS
    # -------------------------------------------------

    if payment.status != "captured":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Payment is not captured. "
                f"Current status: {payment.status}"
            ),
        )

    # -------------------------------------------------
    # 8. AUDIT VERIFIED PAYMENT
    # -------------------------------------------------

    record_audit_event(
        transaction_id=transaction_id,
        event_type="payment_verification",
        status="verified",
        details={
            "order_id": razorpay_order_id,
            "payment_id": razorpay_payment_id,
            "amount_paise": payment.amount_paise,
            "currency": payment.currency,
            "payment_status": payment.status,
        },
    )

    # -------------------------------------------------
    # 9. FULFILL ORDER
    # -------------------------------------------------

    fulfillment = fulfill_order(
        order_id=razorpay_order_id,
        product_id=expected_order["product_id"],
        quantity=expected_order["quantity"],
    )

    record_audit_event(
        transaction_id=transaction_id,
        event_type="order_fulfillment",
        status=fulfillment.status,
        details={
            "fulfillment_id": fulfillment.fulfillment_id,
            "order_id": fulfillment.order_id,
            "product_id": fulfillment.product_id,
            "quantity": fulfillment.quantity,
            "message": fulfillment.message,
        },
    )

    fulfillment_data = {
        "status": fulfillment.status,
        "fulfillment_id": fulfillment.fulfillment_id,
        "product_id": fulfillment.product_id,
        "quantity": fulfillment.quantity,
        "message": fulfillment.message,
    }

    # -------------------------------------------------
    # 10. MARK PAYMENT AS PROCESSED
    # -------------------------------------------------

    processed_payments[
        razorpay_payment_id
    ] = fulfillment_data

    # -------------------------------------------------
    # FINAL RESPONSE
    # -------------------------------------------------

    return {
        "status": "payment_verified",
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "amount_paise": payment.amount_paise,
        "currency": payment.currency,
        "payment_status": payment.status,
        "fulfillment": {
            "status": fulfillment.status,
            "fulfillment_id": fulfillment.fulfillment_id,
            "product_id": fulfillment.product_id,
            "quantity": fulfillment.quantity,
            "message": fulfillment.message,
        },
    }