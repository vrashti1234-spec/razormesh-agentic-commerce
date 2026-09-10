from __future__ import annotations

from app.protocols.ap2 import CheckoutMandate


class PolicyDecision:
    def __init__(self, allowed: bool, reason: str):
        self.allowed = allowed
        self.reason = reason

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
        }


def evaluate_payment_policy(
    mandate: CheckoutMandate,
    *,
    merchant_id: str,
    product_id: str,
    quantity: int,
    amount_paise: int,
    currency: str,
) -> PolicyDecision:
    """
    Deterministic Trust Boundary.

    The AI agent cannot bypass these checks.
    Payment is allowed only when the proposed payment
    exactly matches the authorized mandate.
    """

    # 1. Merchant check
    if merchant_id != mandate.merchant_id:
        return PolicyDecision(
            False,
            "Merchant does not match authorized merchant",
        )

    # 2. Product check
    if product_id != mandate.product_id:
        return PolicyDecision(
            False,
            "Product is not authorized by the mandate",
        )

    # 3. Quantity check
    if quantity != mandate.quantity:
        return PolicyDecision(
            False,
            "Quantity does not match authorized quantity",
        )

    # 4. Amount check
    if amount_paise != mandate.amount_paise:
        return PolicyDecision(
            False,
            "Payment amount does not match authorized amount",
        )

    # 5. Currency check
    if currency != mandate.currency:
        return PolicyDecision(
            False,
            "Currency does not match authorized currency",
        )

    return PolicyDecision(
        True,
        "Payment satisfies deterministic policy",
    )