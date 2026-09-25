from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
import json
import re

import requests
from ddgs import DDGS


@dataclass
class ProductSearchResult:
    title: str
    url: str
    snippet: str
    source: str


@dataclass
class ResolvedProduct:
    name: str
    url: str
    merchant: str
    price: float
    currency: str
    availability: str | None = None
    delivery: str | None = None


def search_products(query: str, max_results: int = 5) -> list[ProductSearchResult]:
    search_query = f"{query} buy online India price"

    results = DDGS().text(
        search_query,
        region="in-en",
        safesearch="moderate",
        max_results=max_results,
    )

    products = []

    for result in results:
        url = result.get("href", "")
        title = result.get("title", "")
        snippet = result.get("body", "")

        if not url or not title:
            continue

        products.append(
            ProductSearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source=_extract_domain(url),
            )
        )

    return products


def resolve_product(url: str) -> ResolvedProduct:
    """
    Resolve a selected product URL into structured product information.

    IMPORTANT:
    The price must come from the actual product page's structured metadata.
    We never guess a price from the search snippet.
    """

    if not url:
        raise ValueError("Product URL is required.")

    response = requests.get(
        url,
        timeout=15,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            )
        },
    )

    response.raise_for_status()

    html = response.text
    merchant = _extract_domain(url)

    product_data = _extract_json_ld_product(html)

    name = product_data.get("name")
    price = product_data.get("price")
    currency = product_data.get("currency")

    if not name:
        name = _extract_meta_content(html, "og:title")

    if not name:
        raise ValueError(
            "Could not resolve the exact product name from the selected page."
        )

    if price is None:
        raise ValueError(
            "Could not resolve a verified product price from the selected page."
        )

    try:
        price = float(price)
    except (TypeError, ValueError):
        raise ValueError("Resolved product price is not numeric.")

    if price <= 0:
        raise ValueError("Resolved product price must be greater than zero.")

    if not currency:
        currency = "INR"

    availability = product_data.get("availability")

    if availability:
        availability = str(availability).split("/")[-1]

    delivery = _extract_delivery(html)

    return ResolvedProduct(
        name=str(name).strip(),
        url=url,
        merchant=merchant,
        price=price,
        currency=str(currency).upper(),
        availability=availability,
        delivery=delivery,
    )


def _extract_json_ld_product(html: str) -> dict:
    """
    Extract Product/Offer information from JSON-LD structured data.
    """

    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for script in scripts:
        try:
            data = json.loads(script.strip())
        except json.JSONDecodeError:
            continue

        candidates = []

        if isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                candidates.extend(data["@graph"])
            else:
                candidates.append(data)

        elif isinstance(data, list):
            candidates.extend(data)

        for item in candidates:
            if not isinstance(item, dict):
                continue

            item_type = item.get("@type", "")

            if isinstance(item_type, list):
                is_product = "Product" in item_type
            else:
                is_product = item_type == "Product"

            if not is_product:
                continue

            name = item.get("name")
            offers = item.get("offers")

            if isinstance(offers, list):
                offers = offers[0] if offers else None

            price = None
            currency = None
            availability = None

            if isinstance(offers, dict):
                price = offers.get("price")
                currency = offers.get("priceCurrency")
                availability = offers.get("availability")

            if price is not None:
                return {
                    "name": name,
                    "price": price,
                    "currency": currency,
                    "availability": availability,
                }

    return {}


def _extract_meta_content(html: str, property_name: str) -> str | None:
    pattern = (
        r'<meta[^>]+(?:property|name)=["\']'
        + re.escape(property_name)
        + r'["\'][^>]+content=["\']([^"\']+)["\']'
    )

    match = re.search(pattern, html, flags=re.IGNORECASE)

    if match:
        return match.group(1).strip()

    return None


def _extract_delivery(html: str) -> str | None:
    """
    Try to find delivery/shipping text when the page exposes it directly.
    This is informational only; it is not used to authorize payment.
    """

    patterns = [
        r'([^<]{0,100}(?:delivery|deliver by|shipping)[^<]{0,150})',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)

        if match:
            text = re.sub(r"\s+", " ", match.group(1)).strip()

            if text:
                return text[:250]

    return None


def _extract_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain