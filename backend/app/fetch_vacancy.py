from __future__ import annotations

import os
import re
from urllib.parse import quote, urlparse

import httpx
from bs4 import BeautifulSoup

# Cabeceras cercanas a un navegador real (muchos portales bloquean User-Agent genérico / bot).
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en-US,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Fallback cuando el origen devuelve 401/403/429: Jina Reader obtiene la página desde su lado.
# Desactivar con CV_VACANCY_JINA_FALLBACK=0 si no quieres enviar la URL a un servicio externo.
_JINA_READER_BASE = "https://r.jina.ai/"

# Si la respuesta contiene estas cadenas, el sitio (p. ej. Indeed + Cloudflare) bloqueó incluso al proxy.
_BLOCK_HINTS = (
    "target url returned error 403",
    "just a moment...",
    "request blocked",
    "you have been blocked",
    "attention required!",
    "cloudflare",
    "enable javascript",
    "verify you are human",
    "ray id for this request",
)


def _jina_fallback_enabled() -> bool:
    raw = os.environ.get("CV_VACANCY_JINA_FALLBACK", "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def _should_try_jina_fallback(status_code: int) -> bool:
    return status_code in (401, 403, 429)


def _indeed_host(hostname: str) -> bool:
    h = (hostname or "").lower()
    return h == "indeed.com" or h.endswith(".indeed.com")


def _html_to_plain(html: str, max_chars: int = 80_000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:max_chars]


def _response_to_text(r: httpx.Response, max_chars: int = 80_000) -> str:
    ctype = (r.headers.get("content-type") or "").lower()
    body = r.text or ""
    looks_html = "html" in ctype or body.lstrip().startswith("<")
    if not looks_html:
        return body.strip()[:max_chars]
    return _html_to_plain(body, max_chars=max_chars)


def _absolute_url(url: str) -> str:
    u = url.strip()
    parsed = urlparse(u)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("URL inválida: necesita esquema https://")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Solo se admiten URLs http(s)")
    return u


def _jina_request_url(target: str) -> str:
    """
    La URL objetivo debe ir codificada: si concatenamos ?vjk=... sin codificar,
    el ? pasa a ser query de r.jina.ai y se pierde el anuncio (Indeed, etc.).
    """
    return _JINA_READER_BASE + quote(target, safe="")


def _looks_like_fetch_block(text: str) -> bool:
    if not text or len(text.strip()) < 80:
        return True
    low = text.lower()
    return any(h in low for h in _BLOCK_HINTS)


def _paste_instruction(target_url: str) -> str:
    if _indeed_host(urlparse(target_url).hostname or ""):
        return (
            "Indeed bloquea la descarga automática (403 / anti-bot) desde servidores y proxies; "
            "no hay forma fiable de leer el anuncio solo con la URL en este entorno. "
            "Usa el interruptor «Texto de la vacante», abre la oferta en el navegador y pega la descripción completa."
        )
    return (
        "Este sitio bloqueó la descarga automática. "
        "Usa «Texto de la vacante» y pega el enunciado desde el navegador."
    )


async def _fetch_direct(url: str, timeout_s: float) -> str:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout_s,
        headers=_BROWSER_HEADERS,
    ) as client:
        r = await client.get(url)
        r.raise_for_status()
        return _response_to_text(r)


async def _fetch_via_jina(url: str, timeout_s: float) -> str:
    """Lee la URL a través de Jina Reader. target debe estar normalizado (absolute)."""
    target = _absolute_url(url)
    jina_url = _jina_request_url(target)
    headers = {
        "User-Agent": _BROWSER_HEADERS["User-Agent"],
        "Accept": "text/plain,text/markdown,*/*;q=0.8",
    }
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout_s,
        headers=headers,
    ) as client:
        r = await client.get(jina_url)
        r.raise_for_status()
        text = (r.text or "").strip()
        if not text:
            raise RuntimeError("Jina Reader devolvió cuerpo vacío")
        if _looks_like_fetch_block(text):
            raise RuntimeError(_paste_instruction(target))
        return text[:80_000]


async def text_from_url(url: str, timeout_s: float = 25.0) -> str:
    """
    Obtiene texto legible desde una URL.
    1) GET directo con cabeceras de navegador (salvo Indeed: suele fallar siempre → Jina directo).
    2) Si 401/403/429, reintenta vía Jina Reader (URL objetivo codificada).
    3) Si Jina devuelve página de bloqueo, mensaje claro para pegar texto a mano.
    """
    target = _absolute_url(url)
    host = (urlparse(target).hostname or "").lower()
    indeed = _indeed_host(host)

    async def _try_jina() -> str:
        return await _fetch_via_jina(target, timeout_s)

    if indeed and _jina_fallback_enabled():
        try:
            return await _try_jina()
        except Exception as e:
            raise RuntimeError(
                f"{_paste_instruction(target)} Detalle técnico: {e!s}"
            ) from e

    if indeed:
        try:
            return await _fetch_direct(target, timeout_s)
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"No se pudo leer la URL ({e.response.status_code}). "
                f"{_paste_instruction(target)}"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(f"No se pudo conectar: {e!s}") from e

    try:
        return await _fetch_direct(target, timeout_s)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if _jina_fallback_enabled() and _should_try_jina_fallback(code):
            try:
                return await _try_jina()
            except Exception as jina_err:
                raise RuntimeError(
                    f"No se pudo leer la URL ({code}). {_paste_instruction(target)} "
                    f"Detalle: {jina_err!s}"
                ) from jina_err
        raise RuntimeError(
            f"No se pudo leer la URL ({code}). {_paste_instruction(target)}"
        ) from e
    except httpx.RequestError as e:
        raise RuntimeError(f"No se pudo conectar: {e!s}") from e
