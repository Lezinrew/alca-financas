"""Conector de e-mail sobre uma caixa postal SINTÉTICA em disco.

Serve para desenvolvimento local e testes. Lê ``mailbox.json`` e os arquivos
de anexo de um diretório e se comporta como um provedor de verdade naquilo
que costuma dar problema:

* cursores opacos, presos à consulta, com páginas de tamanho variável e
  última página sem cursor;
* anexos que "trafegam" em base64url sem padding (como no Gmail) ou em base64
  padrão, e passam pelo mesmo decodificador do conector MCP;
* MIME e tamanho DECLARADOS que não batem com o conteúdo;
* nomes de arquivo com ``../`` e extensão dupla;
* texto com instruções maliciosas em assunto, corpo e nome de arquivo.

Nada aqui interpreta o conteúdo: tudo é devolvido como dado.

Formato de ``mailbox.json``::

    {
      "mailbox": "rótulo livre",
      "page_sizes": [3, 2, 4],
      "messages": [
        {"id": "m-1", "from": "...", "subject": "...", "date": "2026-09-30T12:00:00Z",
         "body": "...",
         "attachments": [
           {"id": "a-1", "filename": "extrato.ofx", "declared_mime": "application/x-ofx",
            "declared_size": 1234, "file": "files/extrato.ofx",
            "wire_encoding": "base64url_nopad"}
         ]}
      ]
    }
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..errors import AiError
from ..settings import MIB
from ..types import ExecutionContext, canonical_json, iso_utc
from .base import (
    MAX_BODY_CHARS,
    MAX_FILENAME_CHARS,
    MAX_SENDER_CHARS,
    MAX_SNIPPET_CHARS,
    MAX_SUBJECT_CHARS,
    AttachmentBlob,
    AttachmentInfo,
    EmailConnector,
    EmailMessage,
    EmailPage,
    EmailSummary,
    clean_body,
    clean_mime,
    clean_size,
    clean_text,
    decode_base64_payload,
    is_safe_identifier,
    unavailable,
)


_MAILBOX_FILE = "mailbox.json"
_MAX_MAILBOX_BYTES = 2 * MIB
_WIRE_ENCODINGS = ("base64url_nopad", "base64")


def _parse_instant(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):  # ``fromisoformat`` só aceita "Z" a partir do Python 3.11
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class FixtureEmailConnector(EmailConnector):
    def __init__(self, directory: Any, *, max_attachment_bytes: int = 20 * MIB) -> None:
        self._dir = Path(os.path.realpath(str(directory)))
        self._max_attachment_bytes = int(max_attachment_bytes)
        mailbox_path = self._dir / _MAILBOX_FILE
        try:
            if mailbox_path.stat().st_size > _MAX_MAILBOX_BYTES:
                raise ValueError("mailbox.json grande demais")
            document = json.loads(mailbox_path.read_text(encoding="utf-8"))
            self._mailbox = str(document.get("mailbox") or "caixa-sintetica")
            self._page_sizes = [int(size) for size in (document.get("page_sizes") or [5])]
            if not self._page_sizes or any(size < 1 for size in self._page_sizes):
                raise ValueError("page_sizes inválido")
            messages = document["messages"]
            if not isinstance(messages, list):
                raise ValueError("messages inválido")
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise unavailable("A caixa postal de teste não pôde ser carregada.") from None

        # Mais recentes primeiro, como os provedores devolvem.
        def sort_key(message: Dict[str, Any]):
            instant = _parse_instant(message.get("date"))
            return (instant or datetime.min.replace(tzinfo=timezone.utc), str(message.get("id")))

        self._messages: List[Dict[str, Any]] = sorted(
            [message for message in messages if isinstance(message, dict) and is_safe_identifier(message.get("id"))],
            key=sort_key,
            reverse=True,
        )
        # Sal dos cursores: muda de caixa para caixa, então um cursor emitido
        # por uma caixa não vale em outra.
        self._salt = hashlib.sha256(("fixture-mailbox|%s" % self._mailbox).encode("utf-8")).hexdigest()

    # -- busca ------------------------------------------------------------

    @staticmethod
    def _haystack(message: Dict[str, Any]) -> str:
        parts = [str(message.get("subject") or ""), str(message.get("body") or ""), str(message.get("from") or "")]
        for attachment in message.get("attachments") or []:
            parts.append(str(attachment.get("filename") or ""))
        return " ".join(parts).casefold()

    @classmethod
    def _matches(cls, message: Dict[str, Any], query: str) -> bool:
        """Subconjunto da sintaxe de busca: termos, ``OR``, ``has:attachment`` e ``filename:``."""
        haystack = cls._haystack(message)
        attachments = message.get("attachments") or []
        groups = [group for group in query.split(" OR ") if group.strip()]
        if not groups:
            return True
        for group in groups:
            matched = True
            for term in group.split():
                lowered = term.casefold()
                if lowered == "has:attachment":
                    matched = bool(attachments)
                elif lowered.startswith("filename:"):
                    needle = lowered[len("filename:"):]
                    matched = any(needle in str(item.get("filename") or "").casefold() for item in attachments)
                else:
                    matched = lowered in haystack
                if not matched:
                    break
            if matched:
                return True
        return False

    def _select(self, query: str, after: Optional[date], before: Optional[date], sender: Optional[str]):
        selected = []
        for message in self._messages:
            instant = _parse_instant(message.get("date"))
            day = instant.date() if instant else None
            # Mesma semântica do Gmail: ``after`` inclui o dia, ``before`` exclui.
            if after is not None and (day is None or day < after):
                continue
            if before is not None and (day is None or day >= before):
                continue
            if sender and sender.casefold() not in str(message.get("from") or "").casefold():
                continue
            if not self._matches(message, query):
                continue
            selected.append(message)
        return selected

    def _cursor_token(self, query_key: str, offset: int) -> str:
        digest = hashlib.sha256(("%s|%s|%d" % (self._salt, query_key, offset)).encode("utf-8")).hexdigest()
        return "fx%s" % digest[:40]

    def _page_bounds(self, total: int) -> List[int]:
        """Início de cada página: os tamanhos variam de uma página para outra."""
        bounds, offset, index = [0], 0, 0
        while True:
            offset += self._page_sizes[index % len(self._page_sizes)]
            if offset >= total:
                return bounds
            bounds.append(offset)
            index += 1

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
        selected = self._select(query or "", after, before, sender)
        query_key = canonical_json({"q": query, "a": after, "b": before, "s": sender})
        bounds = self._page_bounds(len(selected))
        page_index = 0
        if cursor is not None:
            # O cursor não carrega a posição em claro: só "bate" se tiver sido
            # emitido por esta caixa para esta mesma consulta.
            page_index = next(
                (index for index, start in enumerate(bounds) if self._cursor_token(query_key, start) == cursor),
                -1,
            )
            if page_index <= 0:
                raise AiError("invalid_request", "Cursor de busca inválido ou expirado.")
        start = bounds[page_index]
        end = bounds[page_index + 1] if page_index + 1 < len(bounds) else len(selected)
        items = [self._summary(message) for message in selected[start:end]]
        next_cursor = self._cursor_token(query_key, end) if end < len(selected) else None
        return EmailPage(items=items, next_cursor=next_cursor)

    def _summary(self, message: Dict[str, Any]) -> EmailSummary:
        instant = _parse_instant(message.get("date"))
        return EmailSummary(
            message_id=str(message["id"]),
            sender=clean_text(message.get("from"), MAX_SENDER_CHARS),
            subject=clean_text(message.get("subject"), MAX_SUBJECT_CHARS),
            date=iso_utc(instant) if instant else None,
            snippet=clean_text(message.get("body"), MAX_SNIPPET_CHARS),
            has_attachments=bool(message.get("attachments")),
        )

    # -- leitura ----------------------------------------------------------

    def _find_message(self, message_id: str) -> Dict[str, Any]:
        for message in self._messages:
            if message["id"] == message_id:
                return message
        raise AiError("not_found", "Mensagem não encontrada.")

    def get_message(self, ctx: ExecutionContext, message_id: str) -> EmailMessage:
        message = self._find_message(message_id)
        instant = _parse_instant(message.get("date"))
        body, truncated = clean_body(message.get("body"), MAX_BODY_CHARS)
        attachments = []
        for attachment in message.get("attachments") or []:
            if not isinstance(attachment, dict) or not is_safe_identifier(attachment.get("id")):
                continue
            attachments.append(
                AttachmentInfo(
                    attachment_id=attachment["id"],
                    # Nome exatamente como o provedor declarou (pode ter "../").
                    filename=str(attachment.get("filename") or "")[:MAX_FILENAME_CHARS],
                    declared_mime=clean_mime(attachment.get("declared_mime")),
                    size_hint=clean_size(attachment.get("declared_size")),
                )
            )
        return EmailMessage(
            message_id=message["id"],
            sender=clean_text(message.get("from"), MAX_SENDER_CHARS),
            subject=clean_text(message.get("subject"), MAX_SUBJECT_CHARS),
            date=iso_utc(instant) if instant else None,
            body_text=body,
            body_truncated=truncated,
            attachments=attachments,
        )

    # -- anexo ------------------------------------------------------------

    def _attachment_path(self, relative: Any) -> Path:
        # O caminho vem do ``mailbox.json`` (confiável), mas mesmo assim fica
        # preso ao diretório da caixa.
        if not isinstance(relative, str) or not relative:
            raise unavailable("A caixa postal de teste tem um anexo sem arquivo.")
        path = Path(os.path.realpath(str(self._dir / relative)))
        if self._dir != path and self._dir not in path.parents:
            raise unavailable("A caixa postal de teste aponta para fora do diretório.")
        return path

    def download_attachment(self, ctx: ExecutionContext, message_id: str, attachment_id: str) -> AttachmentBlob:
        message = self._find_message(message_id)
        attachment = next(
            (item for item in message.get("attachments") or [] if item.get("id") == attachment_id),
            None,
        )
        if attachment is None:
            raise AiError("not_found", "Anexo não encontrado.")
        path = self._attachment_path(attachment.get("file"))
        try:
            size = path.stat().st_size
            # Não lê para a memória um arquivo que já se sabe ser grande demais
            # (folga de 1 byte para que o limite seja decidido pelo decodificador).
            if size > self._max_attachment_bytes + 1:
                raise AiError("payload_too_large", "O anexo excede o tamanho permitido.")
            raw = path.read_bytes()
        except OSError:
            raise unavailable("A caixa postal de teste não conseguiu ler o anexo.") from None

        wire_encoding = attachment.get("wire_encoding") or "base64url_nopad"
        if wire_encoding not in _WIRE_ENCODINGS:
            raise unavailable("A caixa postal de teste usa uma codificação desconhecida.")
        if wire_encoding == "base64url_nopad":
            wire = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        else:
            wire = base64.b64encode(raw).decode("ascii")
        del raw
        content = decode_base64_payload(wire, self._max_attachment_bytes)
        return AttachmentBlob(
            content=content,
            filename=str(attachment.get("filename") or "anexo")[:MAX_FILENAME_CHARS],
            declared_mime=clean_mime(attachment.get("declared_mime")),
        )
