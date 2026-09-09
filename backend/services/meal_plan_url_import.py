"""
Fetch meal-plan / prepared-meal pages (Huel, meal-kit blogs, printable plans)
and turn them into plain text suitable for meal_plan_import.parse_meal_plan_text.
"""
from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from utils.security import is_safe_external_url

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def normalize_meal_plan_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("URL is required")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    is_safe, error = is_safe_external_url(url)
    if not is_safe:
        raise ValueError(error or "URL is not allowed")
    return url


def _html_to_text(html: str, limit: int = 20000) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        element.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:limit]


async def fetch_meal_plan_page_text(url: str, timeout: float = 30.0) -> Tuple[str, str]:
    """
    Fetch a meal-plan / product page and return (plain_text, source_url).
    Tries direct HTML first, then Jina Reader for JS-heavy sites (Huel, etc.).
    """
    url = normalize_meal_plan_url(url)
    text = ""

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                url, headers=BROWSER_HEADERS, timeout=timeout, follow_redirects=True
            )
            if resp.status_code < 400:
                text = _html_to_text(resp.text)
                logger.info("Meal-plan URL fetch: %s chars from %s", len(text), url)
        except Exception as e:
            logger.warning("Direct meal-plan URL fetch failed for %s: %s", url, e)

        if len(text) < 400:
            try:
                jina_resp = await client.get(
                    f"https://r.jina.ai/{url}",
                    headers={"Accept": "text/plain", "X-Return-Format": "text"},
                    timeout=timeout,
                    follow_redirects=True,
                )
                if jina_resp.status_code == 200 and jina_resp.text:
                    jina_text = jina_resp.text.strip()
                    if len(jina_text) > len(text):
                        text = jina_text[:20000]
                        logger.info("Meal-plan URL via Jina: %s chars", len(text))
            except Exception as e:
                logger.warning("Jina meal-plan fetch failed for %s: %s", url, e)

    if len(text.strip()) < 80:
        raise ValueError(
            "Could not read enough content from that page. "
            "Try a public meal-plan article URL, or paste/upload the plan instead."
        )
    return text, url


MEAL_PLAN_STRUCTURE_PROMPT = """You convert website meal content into a printable weekly meal plan document.

Output ONLY plain text in this exact shape (no markdown fences):

TITLE LINE
Daily target: … (optional)
Weekly Schedule (optional)
Meal Breakdown
DINNER 1 — Title Here
Served Monday, Wednesday
Ingredients — 1 serving
● Ingredient — 100 g
Method
1. Step one
Macros
400 kcal | 30 g protein | 40 g carbohydrate | 10 g fat

SNACK 1 — Title Here
Served every day
Ingredients
● Item — 50 g
Method
1. Mix and serve
Macros
200 kcal | 20 g protein | 15 g carbohydrate | 5 g fat

Shopping List
● Item — amount

Rules:
- Prefer real product/meal names from the page (Huel meals, ready meals, recipe titles).
- If the page lists products without a weekly schedule, invent a sensible 7-day rotation using those meals (dinners + optional snacks).
- Use day names Monday–Sunday.
- Include macros when the page lists calories/protein/carbs/fat.
- If only a few meals exist, reuse them across days with Served lines.
- Keep ingredients practical; use "1 serving" / "1 pouch" / "1 bottle" when amounts are unclear.
"""


def looks_like_structured_meal_plan(text: str) -> bool:
    """Heuristic: enough structure for parse_meal_plan_text without LLM."""
    if not text or len(text) < 80:
        return False
    # Normalize PDF double-spacing / word-per-line so headings match
    compact = re.sub(r"[ \t]{2,}", " ", text)
    compact = re.sub(r"\n{2,}", "\n", compact)
    dinner_hits = len(
        re.findall(r"(?im)^\s*DINNER\s*\d*\s*[—\-:]|^\s*DINNER\s+\d+\b", compact)
    )
    snack_hits = len(
        re.findall(r"(?im)^\s*SNACK\s*\d*\s*[—\-:]|^\s*SNACK\s+\d+\b", compact)
    )
    lunch_hits = len(re.findall(r"(?im)^\s*LUNCH\b", compact))
    served_hits = len(re.findall(r"(?im)^\s*Served\b", compact))
    breakdown = bool(re.search(r"(?im)meal\s+breakdown", compact))
    weekly = bool(re.search(r"(?im)weekly\s+schedule", compact))
    return (
        ((dinner_hits + snack_hits) >= 1 and served_hits >= 1)
        or (breakdown and (dinner_hits + snack_hits) >= 2)
        or (breakdown and lunch_hits >= 1 and (dinner_hits + snack_hits) >= 1)
        or (weekly and breakdown and (dinner_hits + snack_hits + lunch_hits) >= 2)
    )
