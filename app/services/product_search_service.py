from __future__ import annotations

from dataclasses import dataclass
from ddgs import DDGS


@dataclass
class ProductSearchResult:
    title: str
    url: str
    snippet: str
    source: str


def search_products(query: str, max_results: int = 5) -> list[ProductSearchResult]:
    """
    Search the live web for products matching the buyer's request.
    """

    search_query = f"{query} buy online India price"

    results = DDGS().text(
        search_query,
        region="in-en",
        safesearch="moderate",
        max_results=max_results,
    )

    products: list[ProductSearchResult] = []

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


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse

    domain = urlparse(url).netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain