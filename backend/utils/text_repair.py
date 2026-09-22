"""
Reparo de texto com acentuação duplicada ("mojibake").

Caso típico: o OFX do Nubank declara ``CHARSET:1252`` no cabeçalho, mas o corpo
vem em UTF-8. Quem decodifica pelo cabeçalho transforma "débito" em "dÃ©bito"
e "•" em "â€¢" (ou "â\\x80¢").

``repair_mojibake`` só altera o texto quando a reversão produz UTF-8 válido e
reduz os marcadores típicos de mojibake. Texto já correto volta inalterado.
"""
from __future__ import annotations

import re
from typing import Optional

# Sequências que praticamente só aparecem em UTF-8 lido como Latin-1/Windows-1252.
_MOJIBAKE_MARKERS = re.compile(r"[ÃÂ][\x80-\xBFŒœŠšŸŽžƒˆ˜–-™]|â[\x80-\xBF€‘-„•…™]")


def _marker_count(text: str) -> int:
    return len(_MOJIBAKE_MARKERS.findall(text))


def looks_like_mojibake(text: Optional[str]) -> bool:
    return bool(text) and _marker_count(text) > 0


def _reverse(text: str, codec: str) -> Optional[str]:
    try:
        return text.encode(codec).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None


def repair_mojibake(text: Optional[str]) -> Optional[str]:
    """Desfaz uma (ou duas) camadas de UTF-8 decodificado como Latin-1/Windows-1252."""
    if not text or not looks_like_mojibake(text):
        return text
    current = text
    for _ in range(2):
        best = None
        for codec in ("cp1252", "latin-1"):
            candidate = _reverse(current, codec)
            if candidate is not None and _marker_count(candidate) < _marker_count(current):
                best = candidate
                break
        if best is None:
            # Windows-1252 não tem os bytes 0x81/0x8D/0x8F/0x90/0x9D: repara por trecho.
            best = _repair_segments(current)
        if best is None or best == current:
            break
        current = best
        if not looks_like_mojibake(current):
            break
    return current


_SEGMENT = re.compile(r"(?:[Â-ô][\x80-\xBFŒœŠšŸŽžƒˆ˜–-™]{1,3})+")


def _repair_segments(text: str) -> Optional[str]:
    changed = False

    def fix(match: re.Match) -> str:
        nonlocal changed
        chunk = match.group(0)
        for codec in ("cp1252", "latin-1"):
            candidate = _reverse(chunk, codec)
            if candidate is not None:
                changed = True
                return candidate
        return chunk

    result = _SEGMENT.sub(fix, text)
    return result if changed else None
