"""RAG lexical em PostgreSQL com isolamento por tenant, espaço e ACL.

Contrato, seção 10: cada trecho carrega tenant, espaço, ACL, fonte, hash,
versão e datas; o filtro acontece ANTES da busca e DE NOVO antes da entrega;
fonte revogada sai do índice; conteúdo antigo não prevalece sobre o atual.

Por que lexical (``tsvector`` em português) e não vetorial? Não exige modelo de
embeddings nem extensão extra, roda no mesmo PostgreSQL com as mesmas políticas
de RLS e é suficiente para notas e regras pessoais. Números financeiros não
saem daqui: o RAG devolve trechos de texto com fonte; valores vêm de
``finance.read``.

Sobre credenciais: a indexação só aceita texto entregue por uma ferramenta ou
serviço do backend (nota do titular, regra, texto extraído de um anexo em
quarentena). Não existe caminho do modelo para ``index_document`` e este módulo
não lê cofre, token nem variável de ambiente. Quem chama é responsável por não
entregar segredo como conteúdo.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from .db import scoped_tx, write_audit
from .errors import AiError
from .runs import has_control_chars, replace_control_chars
from .types import ExecutionContext, iso_utc


logger = logging.getLogger("ai.rag")

SOURCE_KINDS = ("note", "rule", "artifact", "import")
CONTENT_MAX_CHARS = 200000
TITLE_MAX_CHARS = 200
SOURCE_REF_MAX_CHARS = 300
QUESTION_MAX_CHARS = 500
CHUNK_TARGET_CHARS = 800
SEARCH_DEFAULT_LIMIT = 5
SEARCH_MAX_LIMIT = 10
# A busca traz mais candidatos do que entrega: a rechecagem pode descartar alguns.
_CANDIDATE_FACTOR = 3

_PARAGRAPH = re.compile(r"\n\s*\n")
# Usado com ``fullmatch``: com ``match`` e "$", uma quebra de linha final
# passaria ("nota:x\n"). Sem espaços, controles, DEL nem substitutos isolados.
_SOURCE_REF = re.compile(r"[^\s\x00-\x1f\x7f\ud800-\udfff]{1,%d}" % SOURCE_REF_MAX_CHARS)


def _as_uuid(value: Any) -> Optional[str]:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def split_chunks(content: str, target: int = CHUNK_TARGET_CHARS) -> List[str]:
    """Divide o texto em trechos de até ``target`` caracteres.

    Respeita parágrafos quando cabem; parágrafo grande é cortado em limite de
    palavra. Trechos curtos demais prejudicam a busca (pouco contexto) e
    trechos longos demais poluem o prompt; 800 caracteres é o ponto de partida.
    """
    chunks: List[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for paragraph in _PARAGRAPH.split(content):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > target:
            flush()
            piece = ""
            for word in paragraph.split():
                while len(word) > target:  # "palavra" sem espaços maior que o trecho
                    if piece:
                        chunks.append(piece)
                        piece = ""
                    chunks.append(word[:target])
                    word = word[target:]
                if piece and len(piece) + 1 + len(word) > target:
                    chunks.append(piece)
                    piece = word
                else:
                    piece = "%s %s" % (piece, word) if piece else word
            if piece:
                chunks.append(piece)
            continue
        if current and len(current) + 2 + len(paragraph) > target:
            flush()
        current = "%s\n\n%s" % (current, paragraph) if current else paragraph
    flush()
    return chunks


def _validate_document(source_kind: Any, source_ref: Any, title: Any, content: Any,
                       document_date: Any) -> None:
    if source_kind not in SOURCE_KINDS:
        raise AiError("invalid_request", "Tipo de fonte inválido.", details={"field": "source_kind"})
    if not isinstance(source_ref, str) or _SOURCE_REF.fullmatch(source_ref) is None:
        raise AiError("invalid_request", "Referência da fonte inválida.", details={"field": "source_ref"})
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= TITLE_MAX_CHARS:
        raise AiError("invalid_request", "Título inválido.", details={"field": "title"})
    if has_control_chars(title) or "\n" in title or "\r" in title:
        # O título é uma linha de texto mostrada ao titular como rótulo da fonte.
        raise AiError("invalid_request", "Título inválido.", details={"field": "title"})
    if not isinstance(content, str) or not content.strip():
        raise AiError("invalid_request", "Conteúdo vazio.", details={"field": "content"})
    if len(content) > CONTENT_MAX_CHARS:
        raise AiError("payload_too_large", "O documento excede o tamanho permitido para indexação.")
    if document_date is not None and not isinstance(document_date, date):
        raise AiError("invalid_request", "Data do documento inválida.", details={"field": "document_date"})


def _normalize_acl(acl_user_ids: Optional[Sequence[str]]) -> Optional[List[str]]:
    if acl_user_ids is None:
        return None
    normalized = sorted({item for item in (_as_uuid(value) for value in acl_user_ids) if item})
    if not normalized or len(normalized) != len(set(str(value) for value in acl_user_ids)):
        # Lista vazia NÃO significa "todos": seria fácil abrir um documento por
        # engano. "Todos os membros do espaço" é ``None``, explícito.
        raise AiError("invalid_request", "Lista de acesso inválida.", details={"field": "acl_user_ids"})
    return normalized


def index_document(
    pool,
    ctx: ExecutionContext,
    *,
    source_kind: str,
    source_ref: str,
    title: str,
    content: str,
    document_date: Optional[date] = None,
    acl_user_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Indexa (ou reindexa) um documento no espaço do contexto.

    A mesma ``source_ref`` com conteúdo diferente gera uma nova versão; a
    versão anterior é revogada e seus trechos saem do índice na mesma
    transação, para que conteúdo antigo nunca concorra com o atual. Reindexar
    conteúdo idêntico não muda nada (``unchanged=True``).

    Quem pode substituir: se a versão vigente é restrita (tem ACL), só quem
    está na ACL. Caso contrário, qualquer membro do espaço trocaria — e
    tornaria público — um documento que não consegue nem ler.
    """
    if isinstance(content, str):
        # Texto extraído de PDF/OCR pode trazer NUL e outros controles. O
        # PostgreSQL recusa NUL; o conteúdo é limpo ANTES do hash e da divisão
        # em trechos, então reindexar o mesmo arquivo dá o mesmo hash.
        content = replace_control_chars(content)
    _validate_document(source_kind, source_ref, title, content, document_date)
    acl = _normalize_acl(acl_user_ids)
    title = title.strip()
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    chunks = split_chunks(content)
    if not chunks:
        raise AiError("invalid_request", "Conteúdo vazio.", details={"field": "content"})

    with scoped_tx(pool, ctx.tenant_id) as cursor:
        # Serializa indexações concorrentes da mesma fonte (numeração de versão).
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            ("ai_rag:%s:%s:%s" % (ctx.tenant_id, ctx.financial_space_id, source_ref),),
        )
        if acl is not None:
            cursor.execute(
                """
                SELECT count(*) AS total FROM financial_space_members
                WHERE tenant_id = %s AND financial_space_id = %s AND user_id = ANY(%s::uuid[])
                """,
                (ctx.tenant_id, ctx.financial_space_id, acl),
            )
            if cursor.fetchone()["total"] != len(acl):
                raise AiError(
                    "invalid_request",
                    "A lista de acesso tem pessoas que não participam deste espaço.",
                    details={"field": "acl_user_ids"},
                )
        # Mesma regra de ``revoke_document``: documento restrito só é alterado
        # por quem está na ACL dele. A checagem vem antes de qualquer leitura
        # da versão vigente, para que um ator de fora não descubra nada sobre
        # ela (nem o id, nem se o conteúdo é igual ao que ele enviou).
        cursor.execute(
            """
            SELECT count(*) AS total FROM ai_rag_documents
            WHERE tenant_id = %s AND financial_space_id = %s AND source_ref = %s
              AND revoked_at IS NULL
              AND acl_user_ids IS NOT NULL AND NOT (%s::uuid = ANY(acl_user_ids))
            """,
            (ctx.tenant_id, ctx.financial_space_id, source_ref, ctx.actor_id),
        )
        if cursor.fetchone()["total"] > 0:
            logger.info("rag_index_denied reason=acl")
            raise AiError(
                "conflict",
                "Esta referência já pertence a um documento ao qual você não tem acesso.",
            )
        cursor.execute(
            """
            SELECT id, version, content_hash, acl_user_ids::text[] AS acl_user_ids, title,
                   document_date, revoked_at
            FROM ai_rag_documents
            WHERE tenant_id = %s AND financial_space_id = %s AND source_ref = %s
            ORDER BY version DESC
            LIMIT 1
            """,
            (ctx.tenant_id, ctx.financial_space_id, source_ref),
        )
        latest = cursor.fetchone()
        if latest is not None and latest["revoked_at"] is None:
            current_acl = sorted(str(item) for item in latest["acl_user_ids"]) if latest["acl_user_ids"] else None
            if (
                latest["content_hash"] == content_hash
                and current_acl == acl
                and latest["title"] == title
                and latest["document_date"] == document_date
            ):
                cursor.execute(
                    "SELECT count(*) AS total FROM ai_rag_chunks WHERE tenant_id = %s AND document_id = %s",
                    (ctx.tenant_id, latest["id"]),
                )
                return {
                    "document_id": str(latest["id"]),
                    "version": int(latest["version"]),
                    "content_hash": content_hash,
                    "chunks": int(cursor.fetchone()["total"]),
                    "unchanged": True,
                }
        version = int(latest["version"]) + 1 if latest is not None else 1

        cursor.execute(
            """
            UPDATE ai_rag_documents SET revoked_at = now()
            WHERE tenant_id = %s AND financial_space_id = %s AND source_ref = %s AND revoked_at IS NULL
            RETURNING id
            """,
            (ctx.tenant_id, ctx.financial_space_id, source_ref),
        )
        superseded = [str(row["id"]) for row in cursor.fetchall()]
        if superseded:
            cursor.execute(
                "DELETE FROM ai_rag_chunks WHERE tenant_id = %s AND document_id = ANY(%s::uuid[])",
                (ctx.tenant_id, superseded),
            )
        cursor.execute(
            """
            INSERT INTO ai_rag_documents (
                tenant_id, financial_space_id, created_by_user_id, source_kind, source_ref, title,
                content_hash, version, acl_user_ids, document_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[], %s)
            RETURNING id
            """,
            (
                ctx.tenant_id, ctx.financial_space_id, ctx.actor_id, source_kind, source_ref, title,
                content_hash, version, acl, document_date,
            ),
        )
        document_id = str(cursor.fetchone()["id"])
        for seq, chunk in enumerate(chunks):
            cursor.execute(
                """
                INSERT INTO ai_rag_chunks (tenant_id, financial_space_id, document_id, seq, content)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (ctx.tenant_id, ctx.financial_space_id, document_id, seq, chunk),
            )
        # Auditoria por referência: hash e contagens, nunca o texto indexado.
        write_audit(
            cursor,
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.actor_id,
            event_type="ai.rag.document.indexed",
            entity_type="ai_rag_document",
            entity_id=document_id,
            metadata={
                "financial_space_id": ctx.financial_space_id,
                "source_kind": source_kind,
                "version": version,
                "content_hash": content_hash,
                "chunks": len(chunks),
                "restricted": acl is not None,
                "superseded": superseded,
                "trace_id": ctx.trace_id,
            },
        )
    logger.info("rag_indexed document_id=%s version=%d chunks=%d", document_id, version, len(chunks))
    return {
        "document_id": document_id,
        "version": version,
        "content_hash": content_hash,
        "chunks": len(chunks),
        "unchanged": False,
    }


def revoke_document(pool, ctx: ExecutionContext, document_id: str) -> Dict[str, Any]:
    """Revoga um documento: marca ``revoked_at`` e apaga os trechos do índice.

    Idempotente. Documento de outro tenant, outro espaço ou fora da ACL do ator
    responde ``not_found``.
    """
    parsed = _as_uuid(document_id)
    if parsed is None:
        raise AiError("not_found", "Documento não encontrado.")
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute(
            """
            SELECT id, revoked_at FROM ai_rag_documents
            WHERE id = %s AND tenant_id = %s AND financial_space_id = %s
              AND (acl_user_ids IS NULL OR %s::uuid = ANY(acl_user_ids))
            FOR UPDATE
            """,
            (parsed, ctx.tenant_id, ctx.financial_space_id, ctx.actor_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise AiError("not_found", "Documento não encontrado.")
        already = row["revoked_at"] is not None
        if not already:
            cursor.execute(
                "UPDATE ai_rag_documents SET revoked_at = now() WHERE id = %s AND tenant_id = %s "
                "RETURNING revoked_at",
                (parsed, ctx.tenant_id),
            )
            row = cursor.fetchone()
        cursor.execute(
            "DELETE FROM ai_rag_chunks WHERE tenant_id = %s AND document_id = %s",
            (ctx.tenant_id, parsed),
        )
        removed = cursor.rowcount
        if not already:
            write_audit(
                cursor,
                tenant_id=ctx.tenant_id,
                actor_user_id=ctx.actor_id,
                event_type="ai.rag.document.revoked",
                entity_type="ai_rag_document",
                entity_id=parsed,
                metadata={
                    "financial_space_id": ctx.financial_space_id,
                    "chunks_removed": removed,
                    "trace_id": ctx.trace_id,
                },
            )
    return {"document_id": parsed, "revoked": True, "revoked_at": iso_utc(row["revoked_at"])}


def _candidates(pool, ctx: ExecutionContext, question: str, limit: int) -> List[Dict[str, Any]]:
    """Primeira barreira: o filtro de escopo faz parte da própria busca.

    Tenant, espaço, revogação e ACL estão no ``WHERE`` junto do casamento de
    texto, então um trecho fora do escopo nem entra no ranking. A pergunta em
    linguagem natural vira uma consulta OR entre os termos (``plainto_tsquery``
    usa AND, estrito demais para perguntas); o ranking ordena pela cobertura.
    """
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute(
            """
            WITH q AS (
                SELECT NULLIF(replace(plainto_tsquery('portuguese', %s)::text, '&', '|'), '')::tsquery AS query
            )
            SELECT c.id AS chunk_id, c.document_id, c.seq, c.content,
                   d.title, d.source_kind, d.source_ref, d.version, d.document_date,
                   d.indexed_at, d.content_hash,
                   ts_rank_cd(c.tsv, q.query)::numeric(12, 6) AS score
            FROM ai_rag_chunks c
            JOIN ai_rag_documents d ON d.id = c.document_id AND d.tenant_id = c.tenant_id
            CROSS JOIN q
            WHERE c.tenant_id = %s AND c.financial_space_id = %s
              AND d.tenant_id = %s AND d.financial_space_id = %s
              AND d.revoked_at IS NULL
              AND (d.acl_user_ids IS NULL OR %s::uuid = ANY(d.acl_user_ids))
              AND q.query IS NOT NULL
              AND c.tsv @@ q.query
            ORDER BY score DESC, d.indexed_at DESC, c.document_id, c.seq
            LIMIT %s
            """,
            (
                question,
                ctx.tenant_id, ctx.financial_space_id,
                ctx.tenant_id, ctx.financial_space_id,
                ctx.actor_id,
                int(limit),
            ),
        )
        return [dict(row) for row in cursor.fetchall()]


def _recheck(pool, ctx: ExecutionContext, candidates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Segunda barreira: reconfere cada documento imediatamente antes da entrega.

    Detalhe de driver: o psycopg2 devolve ``uuid[]`` como texto cru
    (``"{a,b}"``) quando o tipo não está registrado. Por isso a ACL é lida como
    ``text[]``: iterar sobre a string compararia caractere por caractere e
    negaria o acesso a todo mundo.

    Roda em uma transação NOVA, então enxerga revogações e trocas de ACL
    confirmadas depois da busca. Também protege contra um candidato vindo de
    cache ou de um índice desatualizado: o que vale é o estado atual do
    documento, não o que a busca viu.
    """
    document_ids = sorted({item for item in (_as_uuid(c.get("document_id")) for c in candidates) if item})
    if not document_ids:
        return []
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute(
            """
            SELECT d.id, d.tenant_id, d.financial_space_id, d.revoked_at,
                   d.acl_user_ids::text[] AS acl_user_ids, d.version,
                   NOT EXISTS (
                       SELECT 1 FROM ai_rag_documents n
                       WHERE n.tenant_id = d.tenant_id AND n.financial_space_id = d.financial_space_id
                         AND n.source_ref = d.source_ref AND n.version > d.version
                   ) AS is_latest
            FROM ai_rag_documents d
            WHERE d.tenant_id = %s AND d.id = ANY(%s::uuid[])
            """,
            (ctx.tenant_id, document_ids),
        )
        current = {str(row["id"]): row for row in cursor.fetchall()}

    delivered: List[Dict[str, Any]] = []
    for candidate in candidates:
        document = current.get(str(candidate.get("document_id")))
        if document is None:
            continue
        if str(document["tenant_id"]) != ctx.tenant_id:
            continue
        if str(document["financial_space_id"]) != ctx.financial_space_id:
            continue
        if document["revoked_at"] is not None or not document["is_latest"]:
            continue
        acl = document["acl_user_ids"]
        if acl is not None and ctx.actor_id not in {str(item) for item in acl}:
            continue
        if int(document["version"]) != int(candidate.get("version") or 0):
            continue
        delivered.append(candidate)
    dropped = len(candidates) - len(delivered)
    if dropped:
        logger.info("rag_recheck_dropped count=%d", dropped)
    return delivered


def _public_chunk(row: Dict[str, Any]) -> Dict[str, Any]:
    document_date = row.get("document_date")
    return {
        "chunk_id": str(row["chunk_id"]),
        "document_id": str(row["document_id"]),
        "seq": int(row["seq"]),
        "content": row["content"],
        "title": row["title"],
        "source_kind": row["source_kind"],
        "source_ref": row["source_ref"],
        "version": int(row["version"]),
        "document_date": document_date.isoformat() if document_date is not None else None,
        "indexed_at": iso_utc(row["indexed_at"]),
        "content_hash": row["content_hash"],
        # Relevância como decimal em string: resultados nunca carregam float.
        "score": str(row["score"]),
    }


def search(pool, ctx: ExecutionContext, question: str, *, limit: int = SEARCH_DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    """Trechos relevantes do espaço do contexto, com fonte, data e versão."""
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= QUESTION_MAX_CHARS:
        raise AiError("invalid_request", "Pergunta inválida.", details={"field": "question"})
    if has_control_chars(question):
        # NUL na pergunta faria o driver levantar ValueError, que não é AiError.
        raise AiError("invalid_request", "Pergunta inválida.", details={"field": "question"})
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= SEARCH_MAX_LIMIT:
        raise AiError("invalid_request", "Limite inválido.", details={"field": "limit"})
    candidates = _candidates(pool, ctx, question.strip(), limit * _CANDIDATE_FACTOR)
    delivered = _recheck(pool, ctx, candidates)[:limit]
    return [_public_chunk(row) for row in delivered]
