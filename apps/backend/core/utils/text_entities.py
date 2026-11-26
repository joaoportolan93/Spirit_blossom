"""
Extração pura e segura de entidades textuais (@menções e #hashtags) — Onda 7b.
Zero acesso a banco de dados e regexes sem backtracking exponencial (anti-ReDoS).
"""

import re
import unicodedata
from typing import List

_URL_RE = re.compile(
    r"(?:(?:https?|ftp)://|www\.)(?:[^\s<>()]|\([^\s<>()]*\))+",
    re.IGNORECASE,
)
_MENTION_RE = re.compile(r"(?<![\w._%+\-/])@([a-zA-Z0-9]{3,30})(?![a-zA-Z0-9_])")
_HASHTAG_RE = re.compile(r"(?<![\w&/])#(\w{2,50})(?!\w)")


def _strip_urls(text: str) -> str:
    """Normaliza NFC e substitui URLs por espaços preservando fronteiras de palavras."""
    if not text or not isinstance(text, str):
        return ""
    normalized = unicodedata.normalize("NFC", text)
    return _URL_RE.sub(" ", normalized)


def extract_mentions(text: str) -> List[str]:
    """
    Extrai @usernames válidos ([a-zA-Z0-9]{3,30}) de um texto.
    Ignora e-mails (user@domain.com) e URLs, normaliza para lowercase e deduplica.
    """
    cleaned = _strip_urls(text)
    if not cleaned:
        return []
    matches = _MENTION_RE.findall(cleaned)
    return list(dict.fromkeys(m.lower() for m in matches))


def extract_hashtags(text: str) -> List[str]:
    """
    Extrai #hashtags válidas (Unicode alfanuméricas + _, 2-50 chars, não puramente numéricas).
    Ignora fragmentos de URL (https://...#section), normaliza para lowercase e deduplica.
    """
    cleaned = _strip_urls(text)
    if not cleaned:
        return []
    result: List[str] = []
    seen = set()
    for raw_tag in _HASHTAG_RE.findall(cleaned):
        tag = unicodedata.normalize("NFC", raw_tag.lower())
        if len(tag) < 2 or len(tag) > 50 or not any(ch.isalpha() for ch in tag):
            continue
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result
