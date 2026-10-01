"""Interface substituível de conector de e-mail (contrato, seções 5 e 10).

Três operações, todas de LEITURA: buscar, ler uma mensagem e baixar um anexo.
Não existe -- de propósito -- operação de enviar, apagar, mover, rotular ou
alterar mensagens: o que não está na interface não pode ser pedido pelo modelo
nem "aparecer" porque um servidor passou a anunciar uma ferramenta nova.

Tudo o que um conector devolve é DADO NÃO CONFIÁVEL (assunto, corpo, nome de
arquivo, identificadores). Os helpers deste módulo só limitam tamanho e removem
caracteres de controle; quem decide o que chega ao modelo é
``services.ai.email.tools``.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

from ..errors import AiError
from ..types import ExecutionContext


# Corpo em texto entregue pelo conector: limitado aqui para que nenhuma
# implementação carregue uma mensagem gigante para dentro da execução.
MAX_BODY_CHARS = 8000
MAX_SUBJECT_CHARS = 300
MAX_SENDER_CHARS = 200
MAX_SNIPPET_CHARS = 300
MAX_FILENAME_CHARS = 255
MAX_ITEMS_PER_PAGE = 50
MAX_ATTACHMENTS_PER_MESSAGE = 50

# Identificadores de provedor (mensagem, anexo) são tratados como opacos, mas
# precisam caber neste alfabeto. Sem espaço, aspas ou quebra de linha, um "id"
# não consegue carregar uma frase com instruções para o modelo.
_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:=+/@~-]{1,1024}$")
_MIME = re.compile(r"^[a-z0-9][a-z0-9.+-]{0,63}/[a-z0-9][a-z0-9.+-]{0,63}$")
# Controles C0/C1 e DEL; tab, LF e CR são tratados à parte.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩﻿]")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class AttachmentInfo:
    """Metadados de um anexo, como declarados pelo provedor (não verificados)."""

    attachment_id: str
    filename: str
    declared_mime: Optional[str] = None
    # Tamanho DECLARADO. Pode divergir do real; o limite é aplicado aos bytes.
    size_hint: Optional[int] = None


@dataclass(frozen=True)
class EmailSummary:
    """Candidato devolvido por uma busca."""

    message_id: str
    sender: str = ""
    subject: str = ""
    date: Optional[str] = None  # instante ISO 8601 em UTC, quando conhecido
    snippet: str = ""
    has_attachments: Optional[bool] = None


@dataclass
class EmailPage:
    items: List[EmailSummary] = field(default_factory=list)
    # Cursor OPACO do provedor. ``None`` = última página.
    next_cursor: Optional[str] = None


@dataclass
class EmailMessage:
    message_id: str
    sender: str = ""
    subject: str = ""
    date: Optional[str] = None
    body_text: str = ""
    body_truncated: bool = False
    attachments: List[AttachmentInfo] = field(default_factory=list)


@dataclass(frozen=True)
class AttachmentBlob:
    """Bytes de um anexo já decodificados, ainda NÃO validados.

    ``repr`` não mostra o conteúdo: um log acidental do objeto não pode
    despejar um extrato inteiro.
    """

    content: bytes = field(repr=False)
    filename: str = "anexo"
    declared_mime: Optional[str] = None


class EmailConnector:
    """Contrato de um conector de e-mail. Somente leitura."""

    def search(
        self,
        ctx: ExecutionContext,
        *,
        query: str,
        after: Optional[date] = None,
        before: Optional[date] = None,
        sender: Optional[str] = None,
        cursor: Optional[str] = None,
    ) -> EmailPage:
        raise NotImplementedError

    def get_message(self, ctx: ExecutionContext, message_id: str) -> EmailMessage:
        raise NotImplementedError

    def download_attachment(self, ctx: ExecutionContext, message_id: str, attachment_id: str) -> AttachmentBlob:
        raise NotImplementedError

    def close(self) -> None:
        """Libera recursos locais (conexões HTTP). Não age sobre a caixa."""


class ConnectorAuthError(AiError):
    """O provedor recusou a credencial (ex.: HTTP 401, token revogado).

    É um ``connector_unavailable`` que NÃO adianta repetir. Quem chama o
    conector (``email.tools``) marca a conexão com erro, o que interrompe as
    próximas tarefas dela (AC-05).
    """

    def __init__(self, safe_message: Optional[str] = None) -> None:
        super().__init__(
            "connector_unavailable",
            safe_message or "A caixa de e-mail recusou o acesso. Reconecte a conta.",
            retryable=False,
        )


def unavailable(message: str, *, retryable: bool = False) -> AiError:
    return AiError("connector_unavailable", message, retryable=retryable)


# ---------------------------------------------------------------------------
# Saneamento de valores vindos do provedor.
# ---------------------------------------------------------------------------

def is_safe_identifier(value: object) -> bool:
    return isinstance(value, str) and bool(_IDENTIFIER.match(value))


def clean_text(value: object, max_chars: int) -> str:
    """Texto de uma linha: sem controles, espaços colapsados, tamanho limitado."""
    if not isinstance(value, str):
        return ""
    text = _CONTROL.sub("", value)
    text = _WHITESPACE.sub(" ", text).strip()
    return text[:max_chars]


def clean_body(value: object, max_chars: int = MAX_BODY_CHARS) -> Tuple[str, bool]:
    """Corpo em texto: mantém quebras de linha, remove controles e limita."""
    if not isinstance(value, str):
        return "", False
    # Corta antes de normalizar para não processar megabytes à toa.
    truncated = len(value) > max_chars * 4
    text = value[: max_chars * 4].replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_chars:
        return text[:max_chars], True
    return text, truncated


def clean_mime(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    # "text/csv; charset=utf-8" -> "text/csv"
    candidate = value.split(";", 1)[0].strip().lower()
    return candidate if _MIME.match(candidate) else None


def clean_size(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isdigit() and len(value) <= 15:
        return int(value)
    return None


# ---------------------------------------------------------------------------
# Decodificação de anexos entregues em base64.
# ---------------------------------------------------------------------------

def max_encoded_length(max_bytes: int) -> int:
    """Maior texto base64 que ainda pode caber em ``max_bytes`` decodificados.

    Inclui folga para quebras de linha no estilo MIME (CRLF a cada 76
    caracteres) e para o padding.
    """
    core = ((max_bytes + 2) // 3) * 4
    return core + (core // 76 + 1) * 2 + 4


def decode_base64_payload(encoded: object, max_bytes: int) -> bytes:
    """Decodifica base64 padrão OU base64url, com ou sem padding.

    A especificação MCP só diz "base64"; o Gmail usa base64url sem padding e
    outros servidores usam o alfabeto padrão. Por isso aceitamos os dois.

    O tamanho é conferido no texto CODIFICADO, antes de decodificar: um
    servidor não consegue nos fazer alocar centenas de megabytes só para
    descobrir, depois, que o arquivo passava do limite.
    """
    if not isinstance(encoded, str):
        raise unavailable("O conector devolveu o anexo em um formato inesperado.")
    if len(encoded) > max_encoded_length(max_bytes):
        raise AiError("payload_too_large", "O anexo excede o tamanho permitido.")

    compact = "".join(encoded.split())  # remove quebras de linha e espaços
    core = compact.rstrip("=")
    if len(compact) - len(core) > 2 or len(core) % 4 == 1:
        raise unavailable("O conector devolveu um anexo ilegível.")
    url_safe = "-" in core or "_" in core
    if url_safe and ("+" in core or "/" in core):
        # Mistura dos dois alfabetos não é base64 de ninguém.
        raise unavailable("O conector devolveu um anexo ilegível.")
    if url_safe:
        core = core.replace("-", "+").replace("_", "/")
    padded = core + "=" * (-len(core) % 4)
    try:
        raw = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        raise unavailable("O conector devolveu um anexo ilegível.") from None
    if len(raw) > max_bytes:
        raise AiError("payload_too_large", "O anexo excede o tamanho permitido.")
    return raw
