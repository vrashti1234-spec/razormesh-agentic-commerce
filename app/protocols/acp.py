from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel

from app.agents.merchant_agent import merchant_agent
from app.protocols.ap2 import (
    create_checkout_mandate,
    create_payment_mandate,
)


class ACPCheckoutRequest(BaseModel):
    """
    ACP-style commerce message sent from Buyer Agent
    to Merchant Agent.
    """

    message_id: str
    message_type: Literal["checkout.create"]

    product_query: str
    quantity: int
    customer_request: str


class ACPCheckoutResponse(BaseModel):
    """
    ACP-style response returned by the Merchant side.
    """

    message_id: str
    message_type: Literal["checkout.created"]

    checkout_session_id: str
    status: str


def create_checkout_session(
    product_query: str,
    quantity: int,
    customer_request: str,
) -> dict[str, Any]:

    # -------------------------------------------------
    # 1. Buyer → Merchant ACP commerce message
    # -------------------------------------------------

    checkout_request = ACPCheckoutRequest(
        message_id=f"msg_{uuid4().hex[:12]}",
        message_type="checkout.create",
        product_query=product_query,
        quantity=quantity,
        customer_request=customer_request,
    )

    print(
        "ACP → Merchant:",
        checkout_request.model_dump(),
    )

    # -------------------------------------------------
    # 2. Merchant Agent receives ACP message
    # -------------------------------------------------

    checkout_session_id = f"cs_{uuid4().hex[:12]}"

    merchant_state = {
        "customer_request": checkout_request.customer_request,
        "selected_product": checkout_request.product_query,
        "quantity": checkout_request.quantity,
        "catalog_results": [],
        "cart": None,
    }

    merchant_result = merchant_agent(merchant_state)

    cart = merchant_result["cart"]

    if cart is None:
        response = ACPCheckoutResponse(
            message_id=f"msg_{uuid4().hex[:12]}",
            message_type="checkout.created",
            checkout_session_id=checkout_session_id,
            status="requires_action",
        )

        return {
            "request": checkout_request,
            "response": response,
            "checkout_session_id": checkout_session_id,
            "status": "requires_action",
            "items": merchant_result["catalog_results"],
            "cart": None,
            "mandate": None,
        }

    # -------------------------------------------------
    # 3. Merchant creates authoritative checkout
    # -------------------------------------------------

    amount_paise = int(round(cart.total * 100))
    product = cart.items[0]

    # -------------------------------------------------
    # 4. AP2 Checkout Mandate
    # -------------------------------------------------

    mandate = create_checkout_mandate(
        merchant_id="razormesh_demo_merchant",
        checkout_id=checkout_session_id,
        product_id=product.product_id,
        quantity=product.quantity,
        amount_paise=amount_paise,
        currency=cart.currency,
    )
    payment_mandate = create_payment_mandate(
    merchant_id="razormesh_demo_merchant",
    checkout_id=checkout_session_id,
    checkout_hash=mandate.checkout_hash,
    amount_paise=amount_paise,
    currency=cart.currency,
)

    response = ACPCheckoutResponse(
        message_id=f"msg_{uuid4().hex[:12]}",
        message_type="checkout.created",
        checkout_session_id=checkout_session_id,
        status="authorized",
    )

    print(
        "ACP ← Merchant:",
        response.model_dump(),
    )

    return {
    "request": checkout_request,
    "response": response,
    "checkout_session_id": checkout_session_id,
    "status": "authorized",
    "items": merchant_result["catalog_results"],
    "cart": cart,
    "mandate": mandate,
    "payment_mandate": payment_mandate,
}