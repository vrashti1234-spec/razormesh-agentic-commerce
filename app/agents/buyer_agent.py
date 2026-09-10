import json
import os
from dotenv import load_dotenv
from typing import TypedDict

load_dotenv()

from groq import Groq
from langgraph.graph import StateGraph, END


class BuyerState(TypedDict):
    customer_request: str
    product_query: str
    selected_product: str
    quantity: int
    preferences: list[str]
    constraints: list[str]
    recommendation: str
    recommended_product_id: str


def buyer_agent(state: BuyerState):
    """
    Buyer Agent:
    Uses an LLM to extract structured shopping intent
    from the customer's natural-language request.

    The agent identifies:
    - Product the customer wants
    - Quantity
    - Preferences
    - Explicit constraints such as budget
    """

    customer_request = state["customer_request"].strip()

    print("Buyer Agent received:", customer_request)

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a buyer agent for an agentic commerce system. "
                    "Understand the customer's shopping request and extract "
                    "their purchase intent.\n\n"

                    "Extract:\n"
                    "1. product_query: the product the customer wants\n"
                    "2. quantity: number of units requested\n"
                    "3. preferences: non-mandatory preferences that describe "
                    "what the customer prefers\n"
                    "4. constraints: explicit requirements or limits that "
                    "must be respected, such as budget, price limit, size, "
                    "compatibility, or other hard requirements\n\n"

                    "Do not invent products, preferences, or constraints. "
                    "Only extract information that is present or clearly "
                    "implied by the customer's request.\n\n"

                    "For example, if the customer says: "
                    "'I need 2 noise cancelling headphones for travelling, "
                    "under ₹10k', then product_query should identify noise "
                    "cancelling headphones, quantity should be 2, "
                    "travelling should be a preference, and the ₹10k limit "
                    "should be a constraint.\n\n"

                    "Return only the requested JSON structure."
                ),
            },
            {
                "role": "user",
                "content": customer_request,
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "buyer_intent",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "product_query": {
                            "type": "string"
                        },
                        "quantity": {
                            "type": "integer"
                        },
                        "preferences": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "constraints": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "product_query",
                        "quantity",
                        "preferences",
                        "constraints"
                    ],
                    "additionalProperties": False
                },
            },
        },
    )

    result = json.loads(response.choices[0].message.content)

    quantity = max(int(result["quantity"]), 1)
    product_query = result["product_query"].strip()

    preferences = [
        str(item).strip()
        for item in result["preferences"]
        if str(item).strip()
    ]

    constraints = [
        str(item).strip()
        for item in result["constraints"]
        if str(item).strip()
    ]

    print("Buyer Agent product:", product_query)
    print("Buyer Agent quantity:", quantity)
    print("Buyer Agent preferences:", preferences)
    print("Buyer Agent constraints:", constraints)

    return {
        "customer_request": customer_request,
        "product_query": product_query,
        "selected_product": "",
        "quantity": quantity,
        "preferences": preferences,
        "constraints": constraints,
        "recommendation": "",
        "recommended_product_id": "",
    }


def generate_buyer_recommendation(
    buyer_result: BuyerState,
    catalog: list[dict],
) -> dict:
    """
    Generate a conversational product recommendation.

    The LLM may reason about which catalog product best matches
    the buyer's request, preferences, and constraints.

    IMPORTANT:
    The LLM does not provide or calculate the price.
    Prices come from the canonical merchant catalog supplied
    to this function.
    """

    print("Buyer Agent generating recommendation...")

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a conversational buyer agent in an "
                    "agentic commerce system.\n\n"

                    "Your job is to recommend the best product from the "
                    "provided merchant catalog based on the buyer's request, "
                    "preferences, and constraints.\n\n"

                    "Rules:\n"
                    "1. You may ONLY recommend a product that exists in "
                    "the provided catalog.\n"
                    "2. Never invent a product.\n"
                    "3. Never invent or modify a price.\n"
                    "4. Respect explicit buyer constraints such as budget.\n"
                    "5. Consider buyer preferences when choosing the product.\n"
                    "6. If no catalog product satisfies the buyer's hard "
                    "constraints, say that no suitable product was found.\n"
                    "7. Keep the recommendation concise and conversational.\n"
                    "8. Return only JSON."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "customer_request": buyer_result["customer_request"],
                        "product_query": buyer_result["product_query"],
                        "quantity": buyer_result["quantity"],
                        "preferences": buyer_result["preferences"],
                        "constraints": buyer_result["constraints"],
                        "catalog": catalog,
                    }
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "buyer_recommendation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "recommended_product_id": {
                            "type": "string"
                        },
                        "recommendation": {
                            "type": "string"
                        }
                    },
                    "required": [
                        "recommended_product_id",
                        "recommendation"
                    ],
                    "additionalProperties": False
                },
            },
        },
    )

    result = json.loads(response.choices[0].message.content)

    recommended_product_id = result["recommended_product_id"].strip()
    recommendation = result["recommendation"].strip()

    # -------------------------------------------------
    # Deterministic validation
    # -------------------------------------------------
    catalog_product_ids = {
        str(product["product_id"]).strip()
        for product in catalog
    }

    if recommended_product_id:
        if recommended_product_id not in catalog_product_ids:
            raise ValueError(
                "Buyer Agent recommended a product not present in catalog"
            )

    print(
        "Buyer Agent recommended product:",
        recommended_product_id,
    )
    print(
        "Buyer Agent recommendation:",
        recommendation,
    )

    return {
        "recommended_product_id": recommended_product_id,
        "recommendation": recommendation,
    }


graph = StateGraph(BuyerState)

graph.add_node("buyer_agent", buyer_agent)

graph.set_entry_point("buyer_agent")
graph.add_edge("buyer_agent", END)

buyer_agent_graph = graph.compile()