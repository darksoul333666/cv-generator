from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup


async def text_from_url(url: str, timeout_s: float = 20.0) -> str:
    headers = {
        "User-Agent": "cv-generator/1.0 (local; job application helper)",
        "Accept": "text/html,application/xhtml+xml",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_s, headers=headers) as client:
        r = await client.get(url)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype.lower():
            return r.text[:50_000]

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:80_000]
