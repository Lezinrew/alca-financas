"""Ferramentas auxiliares: ``rag.search_personal`` e ``whatsapp.respond``.

``build_misc_tools`` devolve as definições; quem monta a plataforma as registra
no ``ToolRegistry``. Nada é criado no import.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

from . import rag
from .errors import AiError
from .registry import ToolArgs, ToolDefinition, ToolResult
from .settings import AiSettings
from .types import ExecutionContext, Source


class RagSearchArgs(ToolArgs):
    question: str = Field(min_length=1, max_length=rag.QUESTION_MAX_CHARS)
    limit: Optional[int] = Field(default=None, ge=1, le=rag.SEARCH_MAX_LIMIT)


class WhatsappRespondArgs(ToolArgs):
    conversation_ref: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=2000)


def build_misc_tools(pool, settings: AiSettings) -> List[ToolDefinition]:
    def rag_search(ctx: ExecutionContext, args: RagSearchArgs) -> ToolResult:
        chunks = rag.search(pool, ctx, args.question, limit=args.limit or rag.SEARCH_DEFAULT_LIMIT)
        sources: Dict[str, Source] = {}
        items: List[Dict[str, Any]] = []
        for chunk in chunks:
            ref = "rag:%s:v%d" % (chunk["document_id"], chunk["version"])
            items.append(
                {
                    "source": ref,
                    "title": chunk["title"],
                    "content": chunk["content"],
                    "document_date": chunk["document_date"],
                    "version": chunk["version"],
                    "indexed_at": chunk["indexed_at"],
                    "score": chunk["score"],
                }
            )
            if ref not in sources:
                sources[ref] = Source(
                    ref=ref,
                    kind="rag",
                    label=chunk["title"],
                    as_of=chunk["indexed_at"],
                    extra={
                        "source_kind": chunk["source_kind"],
                        "source_ref": chunk["source_ref"],
                        "document_date": chunk["document_date"],
                        "version": chunk["version"],
                    },
                )
        # Sem ``facts``: trecho de documento não é fato financeiro. Um valor que
        # apareça em uma nota não lastreia o resumo; números vêm de finance.read.
        return ToolResult(data={"count": len(items), "chunks": items}, sources=list(sources.values()))

    def whatsapp_respond(ctx: ExecutionContext, args: WhatsappRespondArgs) -> ToolResult:
        # O vínculo de remetente verificado (contrato, etapa 5) ainda não existe.
        # Sem ele não há como provar a quem a resposta seria entregue; por isso a
        # ferramenta falha de forma explícita em vez de fingir uma entrega.
        raise AiError(
            "connector_unavailable",
            "A resposta por WhatsApp ainda não está disponível.",
            retryable=False,
        )

    return [
        ToolDefinition(
            name="rag.search_personal",
            version="1.0.0",
            description=(
                "Busca trechos nos documentos e notas pessoais do espaço financeiro atual. "
                "Devolve texto com fonte, data e versão. Não devolve valores financeiros."
            ),
            args_model=RagSearchArgs,
            effect="read",
            handler=rag_search,
        ),
        ToolDefinition(
            name="whatsapp.respond",
            version="1.0.0",
            description="Envia uma resposta ao titular pelo WhatsApp em uma conversa já verificada.",
            args_model=WhatsappRespondArgs,
            effect="message",
            handler=whatsapp_respond,
            requires_flags=("whatsapp_enabled",),
        ),
    ]
