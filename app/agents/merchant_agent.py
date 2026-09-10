from __future__ import annotations

import json
import os
import re
from typing import TypedDict

from dotenv import load_dotenv
from groq import Groq

from app.model import Cart, CartItem, Product

load_dotenv()


class CatalogProductView(TypedDict):
    product_id: str
    name: str
    price: float
    currency: str


class MerchantState(TypedDict):
    customer_request: str
    selected_product: str
    quantity: int
    catalog_results: list[CatalogProductView]
    cart: Cart | None


class MerchantDecision(TypedDict):
    product_id: str
    quantity: int


CATALOG: tuple[Product, ...] = (
    Product(
        product_id="prod_hp01",
        name="Noise Cancelling Headphones",
        price=7999.0,
    ),
    Product(
        product_id="prod_kb01",
        name="Mechanical Keyboard",
        price=4499.0,
    ),
    Product(
        product_id="prod_dk01",
        name="USB-C Dock",
        price=6499.0,
    ),
    Product(
        product_id="prod_ssd01",
        name="Portable SSD 1TB",
        price=8999.0,
    ),
)


def list_catalog() -> list[Product]:
    return list(CATALOG)


def get_product_by_id(product_id: str) -> Product | None:
    normalized_product_id = _normalize_text(product_id)

    for product in CATALOG:
        if product.product_id.lower() == normalized_product_id:
            return product

    return None


def search_catalog(query: str) -> list[Product]:
    normalized_query = _normalize_text(query)

    if not normalized_query:
        return list_catalog()

    query_tokens = set(_tokenize(query))
    ranked_matches: list[tuple[tuple[int, int, int], int, Product]] = []

    for index, product in enumerate(CATALOG):
        normalized_name = _normalize_text(product.name)
        name_tokens = set(_tokenize(product.name))

        exact_id_match = normalized_query == product.product_id.lower()
        exact_name_match = normalized_query == normalized_name
        substring_match = normalized_query in normalized_name
        token_overlap = len(query_tokens & name_tokens)

        if (
            exact_id_match
            or exact_name_match
            or substring_match
            or token_overlap
        ):
            score = (
                int(exact_id_match or exact_name_match),
                int(substring_match),
                token_overlap,
            )

            ranked_matches.append((score, index, product))

    ranked_matches.sort(
        key=lambda item: (
            -item[0][0],
            -item[0][1],
            -item[0][2],
            item[1],
        )
    )

    return [product for _, _, product in ranked_matches]


def build_cart(product: Product, quantity: int) -> Cart:
    """
    Deterministic cart creation.

    The LLM never supplies the price.
    Price always comes from the canonical merchant catalog.
    """

    if quantity < 1:
        raise ValueError("Quantity must be at least 1")

    line_total = product.price * quantity

    item = CartItem(
        product_id=product.product_id,
        name=product.name,
        quantity=quantity,
        unit_price=product.price,
        line_total=line_total,
        currency=product.currency,
    )

    return Cart(
        items=[item],
        total=line_total,
        currency=product.currency,
    )


def merchant_agent(state: MerchantState):
    """
    Real LLM-backed Merchant Agent.

    The LLM identifies which catalog product best matches
    the buyer's request.

    Deterministic code then validates the product and
    calculates the actual price/cart.
    """

    customer_request = state["customer_request"].strip()
    product_query = state["selected_product"].strip()
    requested_quantity = max(state["quantity"], 1)

    print("Merchant Agent received:", product_query)

    catalog_for_llm = [
        {
            "product_id": product.product_id,
            "name": product.name,
        }
        for product in CATALOG
    ]

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the merchant agent for an agentic commerce "
                    "system. Match the buyer's requested product to the "
                    "merchant catalog. You may ONLY select a product_id "
                    "that exists in the provided catalog. Never invent "
                    "products or prices. Return only JSON."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "customer_request": customer_request,
                        "product_query": product_query,
                        "quantity": requested_quantity,
                        "catalog": catalog_for_llm,
                    }
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "merchant_decision",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string"
                        },
                        "quantity": {
                            "type": "integer"
                        },
                    },
                    "required": [
                        "product_id",
                        "quantity"
                    ],
                    "additionalProperties": False,
                },
            },
        },
    )

    decision: MerchantDecision = json.loads(
        response.choices[0].message.content
    )

    product_id = decision["product_id"]
    quantity = decision["quantity"]

    print("Merchant Agent selected product:", product_id)
    print("Merchant Agent quantity:", quantity)

    # Deterministic validation.
    product = get_product_by_id(product_id)

    if product is None:
        raise ValueError(
            "Merchant Agent selected a product not present in catalog"
        )

    if quantity != requested_quantity:
        raise ValueError(
            "Merchant Agent changed the buyer-authorized quantity"
        )

    # Deterministic pricing.
    cart = build_cart(product, quantity)

    print("Merchant Agent canonical product:", product.name)
    print("Merchant Agent cart total:", cart.total)

    return {
        "customer_request": customer_request,
        "selected_product": product.product_id,
        "quantity": quantity,
        "catalog_results": [
            _serialize_product(product)
        ],
        "cart": cart,
    }


def _serialize_product(product: Product) -> CatalogProductView:
    return {
        "product_id": product.product_id,
        "name": product.name,
        "price": product.price,
        "currency": product.currency,
    }


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _build_merchant_agent_graph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(MerchantState)

    graph.add_node("merchant_agent", merchant_agent)

    graph.set_entry_point("merchant_agent")
    graph.add_edge("merchant_agent", END)

    return graph.compile()


try:
    merchant_agent_graph = _build_merchant_agent_graph()
except ModuleNotFoundError:
    merchant_agent_graph = None
