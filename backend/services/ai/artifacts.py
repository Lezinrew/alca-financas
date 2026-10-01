"""Quarentena privada de anexos (contrato, seção 10).

Todo arquivo que entra pela plataforma de IA (anexo de e-mail, upload,
WhatsApp) passa por ``store_attachment`` antes de qualquer leitura:

1. tamanho: maior que zero e até ``settings.artifact_max_bytes`` (20 MiB);
2. tipo decidido PELO CONTEÚDO. O MIME declarado e a extensão são só
   informação: quem envia o arquivo escolhe os dois;
3. só entram OFX, CSV, PDF, PNG e JPEG. HTML, executável, compactado,
   documento do Office e conteúdo desconhecido são recusados;
4. PDF: no máximo ``settings.pdf_max_pages`` páginas; PDF com senha é
   recusado com orientação de desbloqueio (a senha nunca passa pela conversa);
5. SHA-256 do conteúdo; o mesmo arquivo no mesmo espaço vira o mesmo artefato
   (um reenvio só troca o nome guardado se o antigo não tinha a extensão do
   tipo detectado e o novo tem);
6. gravação em ``<quarentena>/<tenant>/<espaço>/<sha256>``. O nome original,
   saneado, fica só no banco: nenhum texto vindo de fora vira caminho;
7. validade de ``settings.artifact_ttl_days`` dias e auditoria por referência
   (ids, hash, tipo, tamanho), nunca com conteúdo nem nome do arquivo.

Nada aqui executa, renderiza ou segue links do arquivo. O PDF é aberto só
para contar páginas e detectar criptografia.
"""

from __future__ import annotations

import codecs
import csv
import hashlib
import io
import logging
import os
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from psycopg2 import errors as pg_errors

from .db import jsonb, scoped_tx, write_audit
from .email.base import AttachmentBlob, clean_mime
from .errors import AiError
from .settings import AiSettings
from .types import ExecutionContext, iso_utc


logger = logging.getLogger("ai.artifacts")

ALLOWED_KINDS = ("ofx", "csv", "pdf", "png", "jpeg")
SOURCE_KINDS = ("email", "upload", "whatsapp")
# Tipos que são evidência (comprovante), não extrato.
EVIDENCE_KINDS = frozenset({"pdf", "png", "jpeg"})

_COLUMNS = (
    "id, tenant_id, financial_space_id, created_by_user_id, run_id, connection_id, source_kind, "
    "source_ref, original_filename, declared_mime, detected_kind, size_bytes, sha256, storage_key, "
    "state, expires_at, created_at"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SNIFF_BYTES = 64 * 1024
_MAX_FILENAME_CHARS = 120
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩﻿]")
_TEXT_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_FORBIDDEN_NAME_CHARS = re.compile(r'[<>:"|?*]')

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
_PDF = b"%PDF-"
# Assinaturas recusadas. A lista não precisa ser completa (o que não for
# reconhecido como permitido já é recusado); ela existe para dar ao titular
# um motivo claro nos casos mais comuns.
_REFUSED_SIGNATURES = (
    (b"MZ", "executável"),
    (b"\x7fELF", "executável"),
    (b"\xfe\xed\xfa\xce", "executável"),
    (b"\xfe\xed\xfa\xcf", "executável"),
    (b"\xce\xfa\xed\xfe", "executável"),
    (b"\xcf\xfa\xed\xfe", "executável"),
    (b"\xca\xfe\xba\xbe", "executável"),
    (b"#!", "script"),
    (b"PK\x03\x04", "arquivo compactado"),
    (b"PK\x05\x06", "arquivo compactado"),
    (b"PK\x07\x08", "arquivo compactado"),
    (b"\x1f\x8b", "arquivo compactado"),
    (b"7z\xbc\xaf\x27\x1c", "arquivo compactado"),
    (b"Rar!", "arquivo compactado"),
    (b"\xd0\xcf\x11\xe0", "documento do Office"),
)
_HTML_MARKERS = re.compile(
    rb"<!doctype\s+html|<html[\s>]|<head[\s>]|<body[\s>]|<script[\s>]|<iframe[\s>]|<svg[\s>]|<\?php",
    re.IGNORECASE,
)
# MIME declarado compatível com cada tipo detectado. Divergência não recusa o
# arquivo (o conteúdo é quem manda); ela só é sinalizada.
_COMPATIBLE_MIMES = {
    "ofx": {"application/x-ofx", "application/ofx", "text/ofx", "application/vnd.intu.qfx",
            "application/octet-stream", "text/plain", "application/xml", "text/xml"},
    "csv": {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel",
            "application/octet-stream"},
    "pdf": {"application/pdf", "application/octet-stream"},
    "png": {"image/png", "application/octet-stream"},
    "jpeg": {"image/jpeg", "image/jpg", "image/pjpeg", "application/octet-stream"},
}
# Extensões que combinam com cada tipo detectado. O tipo continua sendo
# decidido pelo conteúdo; isto só serve para (a) dar extensão ao nome-marcador
# e (b) reconhecer, em um reenvio, um nome melhor do que o já guardado.
_KIND_EXTENSIONS = {
    "ofx": (".ofx",),
    "csv": (".csv",),
    "pdf": (".pdf",),
    "png": (".png",),
    "jpeg": (".jpg", ".jpeg"),
}
# Nome usado quando quem enviou não informou nenhum (ver ``sanitize_filename``).
_PLACEHOLDER_NAME = "anexo"


def _invalid(message: str, reason: str) -> AiError:
    return AiError("invalid_request", message, details={"reason": reason})


def _name_matches_kind(filename: str, kind: str) -> bool:
    return filename.lower().endswith(_KIND_EXTENSIONS[kind])


def _origin_not_found(constraint: Optional[str]) -> AiError:
    """A execução ou a conexão apontada como origem não existe neste tenant.

    As duas chaves estrangeiras são compostas com ``tenant_id``: um id de
    outro tenant falha igual a um id inexistente, e a resposta é a mesma
    (``not_found``), sem revelar qual dos dois casos ocorreu.
    """
    name = constraint or ""
    if "run_id" in name:
        subject = "A execução de origem"
    elif "connection_id" in name:
        subject = "A conexão de e-mail de origem"
    else:
        subject = "A origem informada"
    return AiError("not_found", "%s não foi encontrada." % subject, details={"reason": "unknown_origin"})


# ---------------------------------------------------------------------------
# Nome de arquivo.
# ---------------------------------------------------------------------------

def sanitize_filename(name: Any) -> str:
    """Nome apresentável e sem componentes de caminho.

    O resultado é guardado no banco e mostrado ao titular. Ele NUNCA é usado
    para montar o caminho em disco (o caminho usa só tenant, espaço e hash);
    mesmo assim removemos ``../`` e separadores para que o nome não engane
    quem o vir depois.
    """
    text = unicodedata.normalize("NFC", name) if isinstance(name, str) else ""
    text = text.replace("\\", "/").split("/")[-1]
    text = _CONTROL.sub("", text)
    text = _FORBIDDEN_NAME_CHARS.sub("_", text)
    text = re.sub(r"\s+", " ", text).strip().strip(".").strip()
    if len(text) > _MAX_FILENAME_CHARS:
        stem, dot, extension = text.rpartition(".")
        if dot and 0 < len(extension) <= 10:
            text = stem[: _MAX_FILENAME_CHARS - len(extension) - 1] + "." + extension
        else:
            text = text[:_MAX_FILENAME_CHARS]
    return text or _PLACEHOLDER_NAME


# ---------------------------------------------------------------------------
# Detecção de tipo pelo conteúdo.
# ---------------------------------------------------------------------------

def _decode_text(sample: bytes, truncated: bool) -> Optional[str]:
    """Texto do início do arquivo, ou ``None`` se não for texto.

    UTF-8 (com ou sem BOM) primeiro; depois Windows-1252 e Latin-1, comuns em
    extratos de bancos brasileiros.
    """
    try:
        if truncated:
            # A amostra pode ter cortado um caractere multibyte no fim.
            text = codecs.getincrementaldecoder("utf-8-sig")().decode(sample, final=False)
        else:
            text = sample.decode("utf-8-sig")
        if not _TEXT_CONTROL.search(text):
            return text
        return None
    except UnicodeDecodeError:
        pass
    for encoding in ("cp1252", "latin-1"):
        try:
            text = sample.decode(encoding)
        except UnicodeDecodeError:
            continue
        if not _TEXT_CONTROL.search(text):
            return text
    return None


def _csv_delimiter(text: str, truncated: bool) -> Optional[str]:
    """Delimitador que divide TODAS as linhas da amostra no mesmo nº de colunas."""
    sample = text
    if truncated and "\n" in sample:
        sample = sample[: sample.rfind("\n")]
    for delimiter in (",", ";", "\t", "|"):
        try:
            rows = [
                row for row in csv.reader(io.StringIO(sample, newline=""), delimiter=delimiter)
                if any(cell.strip() for cell in row)
            ][:200]
        except csv.Error:
            continue
        if len(rows) < 2:
            continue
        widths = {len(row) for row in rows}
        if len(widths) == 1 and next(iter(widths)) >= 2:
            return delimiter
    return None


def detect_kind(content: bytes) -> str:
    """Tipo do arquivo pelo conteúdo: ``ofx``, ``csv``, ``pdf``, ``png`` ou ``jpeg``.

    Levanta ``invalid_request`` com mensagem segura para todo o resto.
    """
    if content.startswith(_PNG):
        return "png"
    if content.startswith(_JPEG):
        return "jpeg"
    if content.startswith(_PDF):
        return "pdf"
    for signature, label in _REFUSED_SIGNATURES:
        if content.startswith(signature):
            raise _invalid("Este tipo de arquivo (%s) não é aceito." % label, "forbidden_type")

    head = content[:_SNIFF_BYTES]
    truncated = len(content) > _SNIFF_BYTES
    if b"\x00" in head:
        raise _invalid("Tipo de arquivo não reconhecido. Envie OFX, CSV, PDF, PNG ou JPEG.", "unknown_type")
    # HTML antes de OFX/CSV: uma página pode conter a palavra "<OFX>" ou
    # vírgulas e mesmo assim não é extrato.
    if _HTML_MARKERS.search(head):
        raise _invalid("Páginas HTML não são aceitas como anexo financeiro.", "forbidden_type")
    text = _decode_text(head, truncated)
    if text is None:
        raise _invalid("Tipo de arquivo não reconhecido. Envie OFX, CSV, PDF, PNG ou JPEG.", "unknown_type")
    upper = text.lstrip().upper()
    if upper.startswith("OFXHEADER") or "<OFX>" in upper:
        return "ofx"
    if _csv_delimiter(text, truncated) is not None:
        return "csv"
    raise _invalid("Tipo de arquivo não reconhecido. Envie OFX, CSV, PDF, PNG ou JPEG.", "unknown_type")


def _pdf_reader_class():
    """``pypdf.PdfReader`` se a biblioteca estiver instalada; senão ``None``.

    ``pypdf`` é opcional (não está em ``requirements.txt``). Sem ela não há
    como contar páginas nem detectar senha, então o PDF é RECUSADO: aceitar
    sem validar seria pior do que não aceitar.
    """
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:  # ImportError ou falha de dependência da própria lib
        return None
    return PdfReader


def _validate_pdf(content: bytes, max_pages: int) -> int:
    reader_class = _pdf_reader_class()
    if reader_class is None:
        raise _invalid(
            "Este ambiente ainda não consegue validar arquivos PDF com segurança. O arquivo foi recusado.",
            "pdf_validation_unavailable",
        )
    try:
        reader = reader_class(io.BytesIO(content), strict=False)
        encrypted = bool(reader.is_encrypted)
    except Exception:
        raise _invalid("O PDF está corrompido ou não pôde ser lido.", "pdf_invalid") from None
    if encrypted:
        # PDFs só com restrição de impressão/cópia abrem com senha vazia.
        try:
            opened = bool(reader.decrypt(""))
        except Exception:
            opened = False
        if not opened:
            raise _invalid(
                "O PDF está protegido por senha. Desbloqueie o arquivo no seu dispositivo e envie de novo. "
                "Não informe a senha na conversa.",
                "pdf_password_protected",
            )
    try:
        pages = len(reader.pages)
    except Exception:
        raise _invalid("O PDF está corrompido ou não pôde ser lido.", "pdf_invalid") from None
    if pages < 1:
        raise _invalid("O PDF não tem páginas.", "pdf_invalid")
    if pages > max_pages:
        raise AiError(
            "payload_too_large",
            "O PDF tem %d páginas; o limite é %d." % (pages, max_pages),
            details={"reason": "pdf_too_many_pages"},
        )
    return pages


# ---------------------------------------------------------------------------
# Armazenamento.
# ---------------------------------------------------------------------------

def _as_uuid(value: Any, missing: AiError) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise missing


def _not_found() -> AiError:
    return AiError("not_found", "Arquivo não encontrado.")


def _scope_parts(tenant_id: str, financial_space_id: str, sha256: str) -> Tuple[str, str, str]:
    """Os três componentes do caminho, validados: uuid, uuid e hash hexadecimal."""
    tenant = _as_uuid(tenant_id, AiError("internal_error"))
    space = _as_uuid(financial_space_id, AiError("internal_error"))
    if not _SHA256.match(sha256 or ""):
        raise AiError("internal_error")
    return tenant, space, sha256


def storage_path(settings: AiSettings, tenant_id: str, financial_space_id: str, sha256: str) -> Path:
    """Caminho em disco de um artefato: só ids validados e o hash."""
    tenant, space, digest = _scope_parts(tenant_id, financial_space_id, sha256)
    return settings.resolved_quarantine_dir() / tenant / space / digest


def _file_matches(path: Path, sha256: str) -> bool:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() == sha256
    except OSError:
        return False


def _write_file(path: Path, content: bytes, sha256: str) -> None:
    """Grava de forma atômica (arquivo temporário + ``os.replace``)."""
    if _file_matches(path, sha256):
        return  # endereçado pelo conteúdo: se já está lá e confere, nada a fazer
    temporary = path.parent / (".%s.%s.tmp" % (sha256[:16], uuid.uuid4().hex))
    try:
        # ``mode`` do mkdir só vale para o último nível; por isso cada nível
        # (raiz, tenant, espaço) é criado em separado, todos privados.
        for directory in (path.parents[2], path.parents[1], path.parents[0]):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(
            str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    except OSError as exc:
        try:
            os.unlink(str(temporary))
        except OSError:
            pass
        logger.error("event=artifact_write_failed error=%s", type(exc).__name__)
        raise AiError("internal_error", "Não foi possível guardar o arquivo em quarentena.") from None


def _safe_source_ref(source_ref: Any) -> Dict[str, Any]:
    """Referências pequenas da origem (ids do conector). Nunca conteúdo."""
    cleaned: Dict[str, Any] = {}
    for key, value in list((source_ref or {}).items())[:8] if isinstance(source_ref, dict) else []:
        if not isinstance(key, str) or not re.match(r"^[a-z][a-z0-9_]{0,39}$", key):
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            cleaned[key] = value
        elif isinstance(value, str):
            cleaned[key] = _CONTROL.sub("", value)[:1024]
    return cleaned


def _public(row: Dict[str, Any], deduplicated: Optional[bool] = None) -> Dict[str, Any]:
    declared = row["declared_mime"]
    record: Dict[str, Any] = {
        "artifact_id": str(row["id"]),
        "sha256": row["sha256"],
        "detected_kind": row["detected_kind"],
        "size_bytes": int(row["size_bytes"]),
        "filename": row["original_filename"],
        "declared_mime": declared,
        # ``None`` = o provedor não declarou tipo.
        "declared_matches": (declared in _COMPATIBLE_MIMES[row["detected_kind"]]) if declared else None,
        "source_kind": row["source_kind"],
        "source_ref": dict(row["source_ref"] or {}),
        "state": row["state"],
        "expires_at": iso_utc(row["expires_at"]),
        "created_at": iso_utc(row["created_at"]),
        "connection_id": str(row["connection_id"]) if row["connection_id"] else None,
        "run_id": str(row["run_id"]) if row["run_id"] else None,
    }
    if deduplicated is not None:
        record["deduplicated"] = deduplicated
    return record


def store_attachment(
    pool,
    ctx: ExecutionContext,
    settings: AiSettings,
    *,
    blob: AttachmentBlob,
    source_kind: str,
    source_ref: Optional[Dict[str, Any]] = None,
    connection_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Valida e guarda um anexo na quarentena. Devolve o registro do artefato.

    Se o mesmo conteúdo já existe neste espaço, devolve o artefato existente
    (``deduplicated: True``) e renova a validade. O nome guardado só muda em
    um caso: o nome antigo não tinha a extensão do tipo detectado e o novo
    tem (ver o comentário no ramo de deduplicação).

    ``run_id`` ou ``connection_id`` que não existem neste tenant respondem
    ``not_found``; nada é gravado.
    """
    content = getattr(blob, "content", None)
    if not isinstance(content, (bytes, bytearray)):
        raise _invalid("Arquivo inválido.", "invalid_blob")
    content = bytes(content)
    size = len(content)
    if size == 0:
        raise _invalid("O arquivo está vazio.", "empty_file")
    if size > settings.artifact_max_bytes:
        raise AiError(
            "payload_too_large",
            "O arquivo excede o limite de %d MiB." % (settings.artifact_max_bytes // (1024 * 1024) or 1),
        )
    if source_kind not in SOURCE_KINDS:
        raise _invalid("Origem de arquivo inválida.", "invalid_source")
    # Id malformado nem chega ao banco (lá viraria um erro cru de conversão).
    run_ref = _as_uuid(run_id, _origin_not_found("run_id")) if run_id else None
    connection_ref = _as_uuid(connection_id, _origin_not_found("connection_id")) if connection_id else None

    kind = detect_kind(content)
    if kind == "pdf":
        _validate_pdf(content, settings.pdf_max_pages)
    sha256 = hashlib.sha256(content).hexdigest()
    filename = sanitize_filename(getattr(blob, "filename", None))
    if filename == _PLACEHOLDER_NAME:
        # Quem enviou não informou nome (acontece com servidores MCP cujo
        # download só traz os bytes). O marcador é NOSSO, então pode levar a
        # extensão do tipo detectado: sem isso um OFX legítimo ficaria como
        # "anexo" e seria recusado adiante por não terminar em ".ofx". Nome
        # informado por quem enviou nunca é alterado aqui.
        filename = _PLACEHOLDER_NAME + _KIND_EXTENSIONS[kind][0]
    declared_mime = clean_mime(getattr(blob, "declared_mime", None))
    path = storage_path(settings, ctx.tenant_id, ctx.financial_space_id, sha256)
    # Caminho absoluto efetivamente gravado. Permite ler o artefato sem
    # receber ``settings`` (ver ``read_artifact``); nenhum componente dele vem
    # de fora: diretório configurado, ids do contexto e hash.
    storage_key = os.path.abspath(str(path))
    ttl_days = int(settings.artifact_ttl_days)

    renamed = False
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        try:
            cursor.execute(
                "INSERT INTO ai_artifacts ("
                " tenant_id, financial_space_id, created_by_user_id, run_id, connection_id, source_kind,"
                " source_ref, original_filename, declared_mime, detected_kind, size_bytes, sha256,"
                " storage_key, expires_at"
                ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now() + make_interval(days => %s)) "
                "ON CONFLICT (tenant_id, financial_space_id, sha256) DO NOTHING RETURNING " + _COLUMNS,
                (
                    ctx.tenant_id, ctx.financial_space_id, ctx.actor_id, run_ref, connection_ref,
                    source_kind, jsonb(_safe_source_ref(source_ref)), filename, declared_mime, kind, size, sha256,
                    storage_key, ttl_days,
                ),
            )
        except pg_errors.ForeignKeyViolation as exc:
            # ``run_id``/``connection_id`` inexistentes (ou de outro tenant).
            # Sem este ``except`` o erro do driver subiria cru e o orquestrador
            # o trataria como falha interna repetível; repetir não resolve.
            # Sair do ``with`` com exceção desfaz a transação; o arquivo ainda
            # não foi gravado em disco.
            constraint = getattr(exc.diag, "constraint_name", None)
            logger.warning("event=artifact_origin_rejected constraint=%s", constraint or "-")
            raise _origin_not_found(constraint) from None
        row = cursor.fetchone()
        deduplicated = row is None
        if deduplicated:
            # Mesmo conteúdo já guardado neste espaço (contrato, seção 10:
            # deduplicação por hash do arquivo).
            cursor.execute(
                "SELECT " + _COLUMNS + " FROM ai_artifacts "
                "WHERE tenant_id = %s AND financial_space_id = %s AND sha256 = %s FOR UPDATE",
                (ctx.tenant_id, ctx.financial_space_id, sha256),
            )
            existing = cursor.fetchone()
            if existing is None:
                raise AiError("internal_error")
            # Artefato já expurgado (ou cujo arquivo sumiu) volta à quarentena.
            revive = existing["state"] == "expired" or not _file_matches(path, sha256)
            # A linha é reaproveitada para sempre (inclusive depois do
            # expurgo). Se o nome nunca pudesse mudar, um OFX que entrou uma
            # vez como "extrato.txt" ficaria impossível de importar neste
            # espaço: reenviar os mesmos bytes como "extrato.ofx" devolveria o
            # nome antigo. A troca só vale em um sentido -- de um nome SEM a
            # extensão do tipo detectado para um nome COM ela -- para que um
            # reenvio com nome ruim (ex.: "x.ofx.exe" vindo de um e-mail
            # malicioso) nunca estrague um nome bom. Artefato ``consumed`` é
            # evidência de um efeito já aplicado e não é tocado.
            stored_kind = existing["detected_kind"]
            renamed = (
                existing["state"] != "consumed"
                and not _name_matches_kind(existing["original_filename"], stored_kind)
                and _name_matches_kind(filename, stored_kind)
            )
            cursor.execute(
                "UPDATE ai_artifacts SET "
                " state = CASE WHEN %s THEN 'quarantined' ELSE state END,"
                # O tipo declarado descreve o mesmo envio que o nome: muda junto.
                " original_filename = CASE WHEN %s THEN %s ELSE original_filename END,"
                " declared_mime = CASE WHEN %s THEN %s ELSE declared_mime END,"
                " expires_at = GREATEST(expires_at, now() + make_interval(days => %s)) "
                "WHERE id = %s AND tenant_id = %s AND financial_space_id = %s RETURNING " + _COLUMNS,
                (existing["state"] == "expired", renamed, filename, renamed, declared_mime, ttl_days,
                 existing["id"], ctx.tenant_id, ctx.financial_space_id),
            )
            row = cursor.fetchone()
            if revive:
                _write_file(path, content, sha256)
        else:
            _write_file(path, content, sha256)
        metadata: Dict[str, Any] = {
            "financial_space_id": ctx.financial_space_id,
            "sha256": sha256,
            "detected_kind": kind,
            "size_bytes": size,
            "source_kind": source_kind,
            "connection_id": connection_ref,
            "run_id": run_ref,
            "trace_id": ctx.trace_id,
        }
        if deduplicated:
            # Só o fato de ter trocado; o nome em si fica fora da auditoria.
            metadata["filename_updated"] = renamed
        write_audit(
            cursor,
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.actor_id,
            event_type="ai.artifact.deduplicated" if deduplicated else "ai.artifact.stored",
            entity_type="ai_artifact",
            entity_id=str(row["id"]),
            metadata=metadata,
        )
        record = _public(row, deduplicated=deduplicated)
    logger.info(
        "event=artifact_stored artifact_id=%s kind=%s size=%d deduplicated=%s source=%s",
        record["artifact_id"], kind, size, str(deduplicated).lower(), source_kind,
    )
    return record


def _read_path(row: Dict[str, Any], ctx: ExecutionContext, settings: Optional[AiSettings]) -> Path:
    """Caminho de leitura, sempre preso a tenant + espaço do contexto + hash."""
    if settings is not None:
        return storage_path(settings, ctx.tenant_id, ctx.financial_space_id, row["sha256"])
    recorded = Path(row["storage_key"])
    # O caminho gravado só vale se terminar exatamente em
    # <tenant do contexto>/<espaço do contexto>/<sha256 da linha>.
    expected = _scope_parts(ctx.tenant_id, ctx.financial_space_id, row["sha256"])
    if not recorded.is_absolute() or tuple(recorded.parts[-3:]) != expected:
        logger.error("event=artifact_storage_key_rejected artifact_id=%s", row["id"])
        raise AiError("internal_error", "O arquivo em quarentena não pôde ser localizado.")
    return recorded


def read_artifact(
    pool,
    ctx: ExecutionContext,
    artifact_id: str,
    settings: Optional[AiSettings] = None,
) -> Tuple[Dict[str, Any], bytes]:
    """Registro e bytes de um artefato, somente dentro do escopo do contexto.

    Artefato de outro tenant ou de outro espaço responde ``not_found``, igual
    a um id inexistente: quem pergunta não descobre que o arquivo existe.

    ``settings`` é opcional. Com ele, o diretório de quarentena vem da
    configuração atual; sem ele, usa-se o caminho gravado no momento do
    armazenamento, depois de conferir que termina em tenant/espaço/hash.
    """
    artifact_id = _as_uuid(artifact_id, _not_found())
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute(
            "SELECT " + _COLUMNS + ", "
            "(state = 'expired' OR (state IN ('quarantined', 'previewed') AND expires_at <= now())) AS is_expired "
            "FROM ai_artifacts WHERE id = %s AND tenant_id = %s AND financial_space_id = %s",
            (artifact_id, ctx.tenant_id, ctx.financial_space_id),
        )
        row = cursor.fetchone()
    if row is None:
        raise _not_found()
    if row["is_expired"]:
        raise AiError("not_found", "O arquivo expirou na quarentena. Baixe ou envie novamente.")
    path = _read_path(row, ctx, settings)
    try:
        content = path.read_bytes()
    except OSError:
        raise AiError(
            "not_found", "O arquivo não está mais disponível na quarentena. Baixe ou envie novamente."
        ) from None
    # O hash é reconferido a cada leitura: arquivo trocado em disco não passa.
    if hashlib.sha256(content).hexdigest() != row["sha256"]:
        logger.error("event=artifact_integrity_mismatch artifact_id=%s", artifact_id)
        raise AiError("internal_error", "O arquivo em quarentena está corrompido.")
    return _public(row), content


# Transições permitidas de estado do artefato.
_TRANSITIONS = {
    "previewed": ("quarantined",),
    "consumed": ("quarantined", "previewed"),
}


def set_artifact_state(cursor, ctx: ExecutionContext, artifact_id: str, new_state: str) -> bool:
    """Avança o estado do artefato na transação de quem chama.

    ``previewed``: uma prévia foi gerada. ``consumed``: o artefato virou
    evidência de um efeito financeiro aplicado e deixa de ser expurgado pela
    retenção de 7 dias (contrato, seção 11). Devolve ``False`` se o artefato
    não estava em um estado de origem válido (inclusive se já estava no
    estado pedido).
    """
    if new_state not in _TRANSITIONS:
        raise ValueError("estado de artefato inválido: %s" % new_state)
    cursor.execute(
        "UPDATE ai_artifacts SET state = %s "
        "WHERE id = %s AND tenant_id = %s AND financial_space_id = %s AND state = ANY(%s)",
        (new_state, _as_uuid(artifact_id, _not_found()), ctx.tenant_id, ctx.financial_space_id,
         list(_TRANSITIONS[new_state])),
    )
    return cursor.rowcount == 1


def purge_expired(pool, tenant_id: str, settings: AiSettings) -> int:
    """Remove do disco os artefatos vencidos de um tenant. Devolve quantos.

    Só expurga ``quarantined`` e ``previewed``. ``consumed`` é evidência de um
    efeito financeiro e fica preservado. A linha permanece (com o hash) como
    registro de que o arquivo existiu; o estado vira ``expired``.
    """
    tenant_id = _as_uuid(tenant_id, AiError("invalid_request", "Organização inválida."))
    purged = 0
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "SELECT id, financial_space_id, sha256 FROM ai_artifacts "
            "WHERE tenant_id = %s AND state IN ('quarantined', 'previewed') AND expires_at <= now() "
            "ORDER BY expires_at FOR UPDATE SKIP LOCKED",
            (tenant_id,),
        )
        for row in cursor.fetchall():
            path = storage_path(settings, tenant_id, str(row["financial_space_id"]), row["sha256"])
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                # Arquivo ainda em disco: mantém o estado para tentar de novo.
                logger.error("event=artifact_purge_failed artifact_id=%s error=%s", row["id"], type(exc).__name__)
                continue
            cursor.execute(
                "UPDATE ai_artifacts SET state = 'expired' WHERE id = %s AND tenant_id = %s",
                (row["id"], tenant_id),
            )
            write_audit(
                cursor,
                tenant_id=tenant_id,
                actor_user_id=None,
                event_type="ai.artifact.purged",
                entity_type="ai_artifact",
                entity_id=str(row["id"]),
                metadata={"financial_space_id": str(row["financial_space_id"]), "sha256": row["sha256"]},
            )
            purged += 1
    logger.info("event=artifacts_purged tenant_id=%s count=%d", tenant_id, purged)
    return purged
