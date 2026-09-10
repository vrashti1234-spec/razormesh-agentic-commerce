from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Mapping

import razorpay

from app.config import Settings, get_settings


class RazorpayServiceError(RuntimeError):
    """Base error for deterministic Razorpay service operations."""


class RazorpayConfigurationError(RazorpayServiceError):
    """Raised when required Razorpay settings are missing."""


class RazorpayAPIError(RazorpayServiceError):
    """Raised when a Razorpay SDK call fails."""


@dataclass(frozen=True, slots=True)
class RazorpayOrderRequest:
    amount_paise: int
    receipt: str
    currency: str = "INR"
    notes: dict[str, str] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        if self.amount_paise <= 0:
            raise ValueError("amount_paise must be greater than 0.")

        receipt = self.receipt.strip()
        if not receipt:
            raise ValueError("receipt must not be empty.")

        return {
            "amount": self.amount_paise,
            "currency": self.currency,
            "receipt": receipt,
            "notes": dict(self.notes),
        }


@dataclass(frozen=True, slots=True)
class RazorpayOrder:
    order_id: str
    amount_paise: int
    currency: str
    receipt: str
    status: str
    notes: dict[str, str]


@dataclass(frozen=True, slots=True)
class RazorpayPayment:
    payment_id: str
    order_id: str | None
    amount_paise: int
    currency: str
    status: str
    method: str | None


class RazorpayService:
    """
    Deterministic boundary around Razorpay execution and verification.

    Agent workflows may propose a payment, but only this service talks to Razorpay.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        client: razorpay.Client | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client or self._build_client(self._settings)

    @property
    def test_mode(self) -> bool:
        return self._settings.razorpay_test_mode

    def create_order(self, request: RazorpayOrderRequest) -> RazorpayOrder:
        payload = request.to_payload()

        try:
            response = self._client.order.create(payload)
        except Exception as exc:
            raise RazorpayAPIError("Failed to create Razorpay order.") from exc

        return self._to_order(response)

    def fetch_order(self, order_id: str) -> RazorpayOrder:
        normalized_order_id = self._require_value(order_id, "order_id")

        try:
            response = self._client.order.fetch(normalized_order_id)
        except Exception as exc:
            raise RazorpayAPIError("Failed to fetch Razorpay order.") from exc

        return self._to_order(response)

    def fetch_payment(self, payment_id: str) -> RazorpayPayment:
        normalized_payment_id = self._require_value(payment_id, "payment_id")

        try:
            response = self._client.payment.fetch(normalized_payment_id)
        except Exception as exc:
            raise RazorpayAPIError("Failed to fetch Razorpay payment.") from exc

        return self._to_payment(response)

    def verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        try:
            self._client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": self._require_value(order_id, "order_id"),
                    "razorpay_payment_id": self._require_value(
                        payment_id,
                        "payment_id",
                    ),
                    "razorpay_signature": self._require_value(
                        signature,
                        "signature",
                    ),
                }
            )
        except Exception:
            return False

        return True

    @staticmethod
    def _build_client(settings: Settings) -> razorpay.Client:
        key_id = settings.razorpay_key_id.strip()
        key_secret = settings.razorpay_key_secret.get_secret_value().strip()

        if not key_id:
            raise RazorpayConfigurationError("RAZORPAY_KEY_ID is not configured.")

        if not key_secret:
            raise RazorpayConfigurationError("RAZORPAY_KEY_SECRET is not configured.")

        return razorpay.Client(auth=(key_id, key_secret))

    @staticmethod
    def _require_value(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} must not be empty.")
        return normalized

    @staticmethod
    def _to_order(raw_order: Mapping[str, Any]) -> RazorpayOrder:
        notes = raw_order.get("notes") or {}

        return RazorpayOrder(
            order_id=str(raw_order["id"]),
            amount_paise=int(raw_order["amount"]),
            currency=str(raw_order["currency"]),
            receipt=str(raw_order.get("receipt") or ""),
            status=str(raw_order.get("status") or "created"),
            notes={str(key): str(value) for key, value in notes.items()},
        )

    @staticmethod
    def _to_payment(raw_payment: Mapping[str, Any]) -> RazorpayPayment:
        order_id = raw_payment.get("order_id")
        method = raw_payment.get("method")

        return RazorpayPayment(
            payment_id=str(raw_payment["id"]),
            order_id=str(order_id) if order_id else None,
            amount_paise=int(raw_payment["amount"]),
            currency=str(raw_payment["currency"]),
            status=str(raw_payment["status"]),
            method=str(method) if method else None,
        )


@lru_cache
def get_razorpay_service() -> RazorpayService:
    return RazorpayService()
