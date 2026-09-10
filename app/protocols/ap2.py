from __future__ import annotations

import base64
import hashlib
import time
from typing import Any

import jwt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Demo merchant signing key
# ---------------------------------------------------------------------------
#
# For this prototype the key exists in memory.
# In production this must come from a secure key-management system.
#

_MERCHANT_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
_MERCHANT_PUBLIC_KEY = _MERCHANT_PRIVATE_KEY.public_key()


# ---------------------------------------------------------------------------
# AP2-aligned Checkout Mandate
# ---------------------------------------------------------------------------

class CheckoutMandate(BaseModel):
    """
    AP2-aligned closed Checkout Mandate.

    The important AP2 concept here is that checkout_hash is derived
    from the merchant-signed checkout JWT.
    """

    vct: str = "mandate.checkout.1"

    merchant_id: str

    product_id: str
    quantity: int

    amount_paise: int
    currency: str = "INR"

    checkout_id: str

    issued_at: int = Field(
        default_factory=lambda: int(time.time())
    )

    expires_at: int

    # Hash of the merchant-signed checkout JWT.
    checkout_hash: str

    # Merchant-signed checkout JWT.
    checkout_jwt: str

    # Signature over the mandate payload.
    signature: str


# ---------------------------------------------------------------------------
# AP2-aligned Payment Mandate
# ---------------------------------------------------------------------------

class PaymentMandate(BaseModel):
    """
    AP2-aligned Payment Mandate.

    This binds the payment authorization to the previously
    authorized checkout.
    """

    vct: str = "mandate.payment.1"

    merchant_id: str

    checkout_id: str

    checkout_hash: str

    amount_paise: int

    currency: str = "INR"

    issued_at: int = Field(
        default_factory=lambda: int(time.time())
    )

    expires_at: int

    signature: str


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _base64url_sha256(value: str) -> str:
    """
    SHA-256 hash encoded using base64url without padding.

    This matches the form expected for AP2-style checkout_hash.
    """

    digest = hashlib.sha256(
        value.encode("utf-8")
    ).digest()

    return base64.urlsafe_b64encode(
        digest
    ).decode("ascii").rstrip("=")


def _sign_bytes(payload: bytes) -> str:
    signature = _MERCHANT_PRIVATE_KEY.sign(
        payload,
        ec.ECDSA(hashes.SHA256()),
    )

    return base64.urlsafe_b64encode(
        signature
    ).decode("ascii").rstrip("=")


def _decode_signature(signature: str) -> bytes:
    padding = "=" * (-len(signature) % 4)

    return base64.urlsafe_b64decode(
        signature + padding
    )


# ---------------------------------------------------------------------------
# Merchant-signed Checkout JWT
# ---------------------------------------------------------------------------

def create_checkout_jwt(
    *,
    merchant_id: str,
    checkout_id: str,
    product_id: str,
    quantity: int,
    amount_paise: int,
    currency: str,
    issued_at: int,
    expires_at: int,
) -> str:
    """
    Create a merchant-signed checkout JWT.

    This is the important AP2-aligned piece:
    the checkout mandate will reference this JWT through checkout_hash.
    """

    payload = {
        "iss": merchant_id,
        "sub": checkout_id,
        "checkout_id": checkout_id,
        "product_id": product_id,
        "quantity": quantity,
        "amount_paise": amount_paise,
        "currency": currency,
        "iat": issued_at,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        _MERCHANT_PRIVATE_KEY,
        algorithm="ES256",
    )


def verify_checkout_jwt(
    checkout_jwt: str,
    *,
    merchant_id: str,
    checkout_id: str,
) -> tuple[bool, str]:

    try:
        payload = jwt.decode(
            checkout_jwt,
            _MERCHANT_PUBLIC_KEY,
            algorithms=["ES256"],
            options={
                "require": [
                    "iss",
                    "sub",
                    "checkout_id",
                    "product_id",
                    "quantity",
                    "amount_paise",
                    "currency",
                    "iat",
                    "exp",
                ]
            },
        )
    except jwt.ExpiredSignatureError:
        return False, "Checkout JWT has expired"

    except jwt.InvalidTokenError:
        return False, "Invalid checkout JWT signature or claims"

    if payload["iss"] != merchant_id:
        return False, "Checkout JWT merchant mismatch"

    if payload["sub"] != checkout_id:
        return False, "Checkout JWT checkout ID mismatch"

    return True, "checkout JWT verified"


# ---------------------------------------------------------------------------
# Checkout hash
# ---------------------------------------------------------------------------

def calculate_checkout_hash(
    checkout_jwt: str,
) -> str:
    """
    AP2-aligned checkout hash.

    IMPORTANT:
    We hash the merchant-signed checkout JWT itself,
    rather than hashing our own reconstructed JSON object.
    """

    return _base64url_sha256(checkout_jwt)


# ---------------------------------------------------------------------------
# Create Checkout Mandate
# ---------------------------------------------------------------------------

def create_checkout_mandate(
    *,
    merchant_id: str,
    checkout_id: str,
    product_id: str,
    quantity: int,
    amount_paise: int,
    currency: str = "INR",
    expires_in_seconds: int = 300,
) -> CheckoutMandate:

    if quantity < 1:
        raise ValueError(
            "Quantity must be at least 1"
        )

    if amount_paise <= 0:
        raise ValueError(
            "Amount must be greater than zero"
        )

    if expires_in_seconds <= 0:
        raise ValueError(
            "Expiration must be greater than zero"
        )

    now = int(time.time())
    expires_at = now + expires_in_seconds

    # Merchant creates the authoritative checkout JWT.
    checkout_jwt = create_checkout_jwt(
        merchant_id=merchant_id,
        checkout_id=checkout_id,
        product_id=product_id,
        quantity=quantity,
        amount_paise=amount_paise,
        currency=currency,
        issued_at=now,
        expires_at=expires_at,
    )

    # AP2-style binding:
    # checkout_hash = hash(checkout_jwt)
    checkout_hash = calculate_checkout_hash(
        checkout_jwt
    )

    mandate_payload = (
        f"{merchant_id}|"
        f"{checkout_id}|"
        f"{product_id}|"
        f"{quantity}|"
        f"{amount_paise}|"
        f"{currency}|"
        f"{checkout_hash}|"
        f"{now}|"
        f"{expires_at}"
    ).encode("utf-8")

    signature = _sign_bytes(
        mandate_payload
    )

    return CheckoutMandate(
        merchant_id=merchant_id,
        product_id=product_id,
        quantity=quantity,
        amount_paise=amount_paise,
        currency=currency,
        checkout_id=checkout_id,
        issued_at=now,
        expires_at=expires_at,
        checkout_hash=checkout_hash,
        checkout_jwt=checkout_jwt,
        signature=signature,
    )


# ---------------------------------------------------------------------------
# Verify Checkout Mandate
# ---------------------------------------------------------------------------

def verify_checkout_mandate(
    mandate: CheckoutMandate,
    *,
    merchant_id: str,
    product_id: str,
    quantity: int,
    amount_paise: int,
    currency: str,
    checkout_id: str,
) -> tuple[bool, str]:

    now = int(time.time())

    # ---------------------------------------------------------------
    # Deterministic field checks
    # ---------------------------------------------------------------

    if mandate.merchant_id != merchant_id:
        return False, "Merchant is not authorized"

    if mandate.product_id != product_id:
        return False, "Product is not authorized"

    if mandate.quantity != quantity:
        return False, "Quantity does not match mandate"

    if mandate.amount_paise != amount_paise:
        return False, "Amount does not match mandate"

    if mandate.currency != currency:
        return False, "Currency does not match mandate"

    if mandate.checkout_id != checkout_id:
        return False, "Checkout ID does not match mandate"

    if now > mandate.expires_at:
        return False, "Checkout mandate has expired"

    # ---------------------------------------------------------------
    # Verify merchant-signed Checkout JWT
    # ---------------------------------------------------------------

    jwt_valid, jwt_reason = verify_checkout_jwt(
        mandate.checkout_jwt,
        merchant_id=merchant_id,
        checkout_id=checkout_id,
    )

    if not jwt_valid:
        return False, jwt_reason

    # ---------------------------------------------------------------
    # Verify checkout_hash
    # ---------------------------------------------------------------

    expected_hash = calculate_checkout_hash(
        mandate.checkout_jwt
    )

    if mandate.checkout_hash != expected_hash:
        return False, "Checkout hash verification failed"

    # ---------------------------------------------------------------
    # Verify mandate signature
    # ---------------------------------------------------------------

    mandate_payload = (
        f"{mandate.merchant_id}|"
        f"{mandate.checkout_id}|"
        f"{mandate.product_id}|"
        f"{mandate.quantity}|"
        f"{mandate.amount_paise}|"
        f"{mandate.currency}|"
        f"{mandate.checkout_hash}|"
        f"{mandate.issued_at}|"
        f"{mandate.expires_at}"
    ).encode("utf-8")

    try:
        _MERCHANT_PUBLIC_KEY.verify(
            _decode_signature(
                mandate.signature
            ),
            mandate_payload,
            ec.ECDSA(hashes.SHA256()),
        )

    except (
        InvalidSignature,
        ValueError,
    ):
        return False, "Cryptographic mandate signature verification failed"

    return True, "authorized"


# ---------------------------------------------------------------------------
# Payment Mandate
# ---------------------------------------------------------------------------

def create_payment_mandate(
    *,
    merchant_id: str,
    checkout_id: str,
    checkout_hash: str,
    amount_paise: int,
    currency: str = "INR",
    expires_in_seconds: int = 300,
) -> PaymentMandate:

    if amount_paise <= 0:
        raise ValueError(
            "Payment amount must be greater than zero"
        )

    now = int(time.time())
    expires_at = now + expires_in_seconds

    payload = (
        f"mandate.payment.1|"
        f"{merchant_id}|"
        f"{checkout_id}|"
        f"{checkout_hash}|"
        f"{amount_paise}|"
        f"{currency}|"
        f"{now}|"
        f"{expires_at}"
    ).encode("utf-8")

    signature = _sign_bytes(
        payload
    )

    return PaymentMandate(
        merchant_id=merchant_id,
        checkout_id=checkout_id,
        checkout_hash=checkout_hash,
        amount_paise=amount_paise,
        currency=currency,
        issued_at=now,
        expires_at=expires_at,
        signature=signature,
    )


def verify_payment_mandate(
    mandate: PaymentMandate,
    *,
    merchant_id: str,
    checkout_id: str,
    checkout_hash: str,
    amount_paise: int,
    currency: str,
) -> tuple[bool, str]:

    now = int(time.time())

    if mandate.merchant_id != merchant_id:
        return False, "Payment merchant mismatch"

    if mandate.checkout_id != checkout_id:
        return False, "Payment checkout ID mismatch"

    if mandate.checkout_hash != checkout_hash:
        return False, "Payment is not bound to authorized checkout"

    if mandate.amount_paise != amount_paise:
        return False, "Payment amount does not match mandate"

    if mandate.currency != currency:
        return False, "Payment currency does not match mandate"

    if now > mandate.expires_at:
        return False, "Payment mandate has expired"

    payload = (
        f"{mandate.vct}|"
        f"{mandate.merchant_id}|"
        f"{mandate.checkout_id}|"
        f"{mandate.checkout_hash}|"
        f"{mandate.amount_paise}|"
        f"{mandate.currency}|"
        f"{mandate.issued_at}|"
        f"{mandate.expires_at}"
    ).encode("utf-8")

    try:
        _MERCHANT_PUBLIC_KEY.verify(
            _decode_signature(
                mandate.signature
            ),
            payload,
            ec.ECDSA(hashes.SHA256()),
        )

    except (
        InvalidSignature,
        ValueError,
    ):
        return False, "Payment mandate signature verification failed"

    return True, "authorized"