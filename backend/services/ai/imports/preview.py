"""Prévia de importação de extrato (contrato, seções 5, 9 e 10; AC-02).

OFX é a fonte canônica do realizado. A prévia de OFX é produzida pelo MESMO
código do importador do produto, ``OfxImportPipeline.process_file``: este
módulo não interpreta OFX. Ele só

* entrega ao importador os bytes do artefato e as chaves já gravadas na conta
  (FITID e ``dedup_key`` das transações V2), para que duplicados contra o
  banco apareçam na prévia;
* converte o resultado para o formato ``ImportPreview``: cada valor vira
  string decimal na borda e os totais são RECALCULADOS em ``Decimal`` a partir
  dos itens (o importador soma ``float``).

CSV não é fonte canônica: é listado para conferência (``canonical=False``) e
não pode ser aplicado como extrato. PDF e imagem são evidência (comprovante),
não extrato: não têm prévia.

Valor que sai do arquivo é DADO NÃO CONFIÁVEL também quando é número: o
importador lê com ``float``, que aceita ``nan``, ``inf`` e ``1e400``. Por isso
todo valor passa por ``_checked_amount`` na borda (finito e dentro do teto do
ledger) antes de virar string decimal ou entrar em uma soma. No OFX, um valor
inválido recusa o arquivo inteiro (importar "o resto" não bateria com o saldo
do banco); no CSV, que é só conferência, a linha vai para ``ignored`` com o
motivo.

A prévia não grava transações, não cria conta nem categoria. O único efeito é
marcar o artefato como ``previewed`` e registrar a auditoria.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from ...import_service import compute_dedup_key as csv_dedup_key
from ...import_service import parse_import_file
from ...ofx_import import OfxImportPipeline
from ..artifacts import EVIDENCE_KINDS, read_artifact, set_artifact_state
from ..db import scoped_tx, write_audit
from ..errors import AiError
from ..imports_types import ImportPreview, PreviewItem
from ..settings import AiSettings
from ..types import ExecutionContext, money_str, to_decimal


logger = logging.getLogger("ai.imports")

# Rótulo que o importador usa para lançamento sem regra de categoria.
_UNCLASSIFIED = "Não classificado"
_UNKNOWN_INSTITUTION = "Desconhecido"
_ZERO = Decimal("0.00")
# Mesmo teto que o componente financeiro aplica antes de gravar (cabe com folga
# em ``numeric(19,2)``). Acima dele o valor não entraria no ledger e, bem antes
# de ``1e30``, ``quantize`` já estoura a precisão do ``Decimal``.
_MAX_AMOUNT = Decimal("999999999999999.99")
_CSV_TYPES = ("income", "expense")


def _account_not_found() -> AiError:
    return AiError("not_found", "Conta não encontrada neste espaço financeiro.")


def _require_account(ctx: ExecutionContext, account_id: Any) -> str:
    """A conta precisa estar entre as permitidas do contexto (resolvidas no servidor)."""
    try:
        normalized = str(uuid.UUID(str(account_id)))
    except (ValueError, AttributeError, TypeError):
        raise _account_not_found()
    # Conta de outro espaço ou de outro tenant responde como inexistente.
    if normalized not in ctx.allowed_account_ids:
        raise _account_not_found()
    return normalized


def _load_account_and_ledger_keys(
    pool, ctx: ExecutionContext, account_id: str
) -> Tuple[Dict[str, Any], Set[str], Set[str]]:
    """Nome/moeda da conta e as chaves de deduplicação já gravadas nela."""
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        # ``accounts`` e ``transactions`` são tabelas de 0001, sem RLS: o filtro
        # por tenant e o vínculo com o espaço são a única barreira aqui.
        cursor.execute(
            """
            SELECT a.name, a.currency
            FROM accounts a
            JOIN financial_space_accounts l ON l.account_id = a.id AND l.tenant_id = a.tenant_id
            WHERE a.id = %s AND a.tenant_id = %s AND l.financial_space_id = %s AND a.archived_at IS NULL
            """,
            (account_id, ctx.tenant_id, ctx.financial_space_id),
        )
        account = cursor.fetchone()
        if account is None:
            raise _account_not_found()
        # Todas as situações contam (inclusive canceladas): os índices únicos
        # de FITID e ``dedup_key`` valem para a conta inteira.
        cursor.execute(
            """
            SELECT fitid, dedup_key FROM transactions
            WHERE tenant_id = %s AND account_id = %s AND (fitid IS NOT NULL OR dedup_key IS NOT NULL)
            """,
            (ctx.tenant_id, account_id),
        )
        rows = cursor.fetchall()
    fitids = {row["fitid"] for row in rows if row["fitid"]}
    dedup_keys = {row["dedup_key"] for row in rows if row["dedup_key"]}
    return dict(account), fitids, dedup_keys


def _checked_amount(value: Any) -> Optional[Decimal]:
    """Valor do arquivo como ``Decimal`` finito e dentro do teto, ou ``None``.

    ``float("nan")`` e ``float("inf")`` são valores válidos para o Python e
    passam pelo importador sem erro. Se chegassem a ``money_str``, ``nan``
    viraria a string ``"NaN"`` (em itens, totais e fatos) e ``inf`` levantaria
    ``decimal.InvalidOperation``, que não é ``AiError``. O sinal é preservado:
    quem chama decide o que fazer com ele.
    """
    try:
        amount = to_decimal(value)
    except ValueError:
        return None
    if not amount.is_finite() or abs(amount) > _MAX_AMOUNT:
        return None
    return amount


def _invalid_ofx_amount() -> AiError:
    return AiError(
        "invalid_request",
        "O extrato tem um lançamento com valor inválido (não numérico ou fora do limite) e não pode ser lido "
        "com segurança. Baixe o arquivo de novo no banco e envie outra vez.",
        details={"reason": "invalid_amount"},
    )


def _ofx_amount(value: Any) -> str:
    """Valor de um OFX como string decimal; valor inválido recusa o arquivo."""
    amount = _checked_amount(value)
    if amount is None:
        raise _invalid_ofx_amount()
    return money_str(amount)


def _totals(items: List[PreviewItem], *, currency: str, parsed: int, duplicates: int, ignored: int,
            ambiguities: int) -> Dict[str, Any]:
    """Totais em ``Decimal`` a partir dos itens já convertidos para string."""
    sums = {"income": _ZERO, "expense": _ZERO, "transfer": _ZERO}
    for item in items:
        sums[item.type] = sums[item.type] + to_decimal(item.amount)
    return {
        "income": money_str(sums["income"]),
        "expense": money_str(sums["expense"]),
        "transfer": money_str(sums["transfer"]),
        # Transferência não entra no resultado líquido.
        "net": money_str(sums["income"] - sums["expense"]),
        "currency": currency,
        "items": len(items),
        "duplicates": duplicates,
        "ignored": ignored,
        "ambiguities": ambiguities,
        "parsed": parsed,
    }


def _period(dates: List[str]) -> Tuple[Optional[str], Optional[str]]:
    valid = sorted(value for value in dates if value)
    return (valid[0], valid[-1]) if valid else (None, None)


# ---------------------------------------------------------------------------
# OFX: importador determinístico do produto.
# ---------------------------------------------------------------------------

def _item_from_ofx(transaction: Dict[str, Any]) -> PreviewItem:
    category = transaction.get("category_name")
    return PreviewItem(
        dedup_key=transaction["dedup_key"],
        occurred_on=transaction["date"],
        description=transaction["description"],
        # ``float`` do importador -> string decimal, sem passar por aritmética
        # e só depois de conferir que é um número finito.
        amount=_ofx_amount(transaction["amount"]),
        type=transaction["type"],
        fitid=transaction.get("fitid") or None,
        nature="transfer" if transaction["type"] == "transfer" else None,
        category_hint=category if category and category != _UNCLASSIFIED else None,
    )


def _preview_ofx(
    ctx: ExecutionContext,
    record: Dict[str, Any],
    content: bytes,
    account_id: str,
    account: Dict[str, Any],
    existing_fitids: Set[str],
    existing_dedup_keys: Set[str],
) -> ImportPreview:
    # Mesmas entradas que a rota de importação do produto passa ao pipeline:
    # nome do arquivo e nome da conta (que entra na ``dedup_key``). As regras
    # de categoria por alias ainda não existem no V2, então o categorizador é
    # o padrão do pipeline.
    result = OfxImportPipeline().process_file(
        content=content,
        filename=record["filename"],
        user_id=ctx.actor_id,
        tenant_id=ctx.tenant_id,
        account_id=account_id,
        account_name=account["name"],
        existing_dedup_keys=existing_dedup_keys,
        existing_fitids=existing_fitids,
    )

    items = [_item_from_ofx(transaction) for transaction in result["transactions_to_insert"]]

    duplicates: List[Dict[str, Any]] = []
    for transaction in result["duplicate_transactions"]:
        item = _item_from_ofx(transaction)
        in_ledger = (item.fitid in existing_fitids) or (item.dedup_key in existing_dedup_keys)
        duplicates.append(
            {
                "item": item.to_dict(),
                # Motivo produzido pelo importador (cita o FITID ou a chave).
                "reason": transaction.get("duplicate_reason") or "Lançamento duplicado.",
                "scope": "ledger" if in_ledger else "file",
            }
        )

    ignored = [
        {
            "occurred_on": entry.get("date"),
            "description": entry.get("description"),
            "amount": _ofx_amount(entry.get("amount") or 0),
            "fitid": entry.get("fitid") or None,
            "reason": entry.get("reason"),
            "nature": entry.get("nature"),
        }
        for entry in result["ignored_transactions"]
    ]

    # "Não classificado" é decisão do importador; aqui só cruzamos a lista dele
    # com os itens válidos (a lista inclui lançamentos que depois caíram como
    # duplicados).
    unclassified = {
        (entry.get("fitid") or None, entry.get("date"), entry.get("type"), _ofx_amount(entry.get("amount") or 0),
         (entry.get("description") or "").strip())
        for entry in result["unclassified_transactions"]
    }
    ambiguities: List[Dict[str, Any]] = []
    for item in items:
        if item.type == "transfer":
            ambiguities.append(
                {
                    "code": "transfer_without_destination",
                    "message": "Transferência sem conta de destino identificada. Indique o destino antes de aplicar.",
                    "item": item.to_dict(),
                }
            )
        elif (item.fitid, item.occurred_on, item.type, item.amount, item.description.strip()) in unclassified:
            ambiguities.append(
                {
                    "code": "unclassified",
                    "message": "Lançamento sem categoria definida.",
                    "item": item.to_dict(),
                }
            )
    if result["total_parsed"] == 0:
        ambiguities.append(
            {"code": "no_transactions", "message": "O arquivo OFX não contém lançamentos.", "item": None}
        )

    ledger = result.get("ledger_reconciliation") or {}
    declared_balance = ledger.get("declared_balance")
    institution = result.get("institution")
    period_start, period_end = _period(
        [item.occurred_on for item in items]
        + [entry["item"]["occurred_on"] for entry in duplicates]
        + [entry["occurred_on"] for entry in ignored]
    )
    return ImportPreview(
        artifact_id=record["artifact_id"],
        artifact_sha256=record["sha256"],
        filename=record["filename"],
        file_kind="ofx",
        account_id=account_id,
        canonical=True,
        items=items,
        duplicates=duplicates,
        ambiguities=ambiguities,
        ignored=ignored,
        totals=_totals(
            items, currency=account["currency"], parsed=int(result["total_parsed"]),
            duplicates=len(duplicates), ignored=len(ignored), ambiguities=len(ambiguities),
        ),
        institution=institution if institution and institution != _UNKNOWN_INSTITUTION else None,
        period_start=period_start,
        period_end=period_end,
        # O saldo declarado também sai do arquivo e também é lido com ``float``.
        declared_balance=_ofx_amount(declared_balance) if declared_balance is not None else None,
    )


# ---------------------------------------------------------------------------
# CSV: só conferência.
# ---------------------------------------------------------------------------

def _decode_csv(content: bytes) -> str:
    """Texto do CSV. Aceita UTF-8 (com ou sem BOM), Windows-1252 e Latin-1.

    O parser do produto só lê UTF-8 sem BOM; normalizamos a codificação aqui,
    na borda, em vez de alterar o parser.
    """
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    for encoding in ("cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            continue
        if not any(ord(char) < 32 and char not in "\t\r\n" or 127 <= ord(char) < 160 for char in text):
            return text
    raise AiError(
        "invalid_request",
        "Não foi possível reconhecer a codificação do CSV. Exporte o arquivo em UTF-8 e envie de novo.",
        details={"reason": "csv_encoding"},
    )


def _csv_date(value: Any) -> Optional[str]:
    """Data local ``AAAA-MM-DD`` de uma linha, ou ``None`` se não for uma data.

    O parser do produto usa ``pandas.to_datetime``, que aceita o texto "NaT" e
    devolve um objeto que É instância de ``datetime`` mas falha em
    ``strftime``. Por isso a conferência é pelo resultado, não pelo tipo.
    """
    try:
        text = value.strftime("%Y-%m-%d")
        date.fromisoformat(text)  # recusa ano com menos de 4 dígitos e afins
    except (AttributeError, TypeError, ValueError):
        return None
    return text


def _preview_csv(
    record: Dict[str, Any],
    content: bytes,
    account_id: str,
    account: Dict[str, Any],
    existing_dedup_keys: Set[str],
) -> ImportPreview:
    text = _decode_csv(content)
    try:
        # O tipo já foi detectado pelo conteúdo; o nome fixo só seleciona o
        # ramo CSV do parser do produto (o nome real pode nem terminar em .csv).
        _, rows = parse_import_file("artefato.csv", text.encode("utf-8"))
    except Exception as exc:
        logger.warning("event=csv_parse_failed artifact_id=%s error=%s", record["artifact_id"], type(exc).__name__)
        raise AiError(
            "invalid_request", "Não foi possível ler os lançamentos deste CSV.", details={"reason": "csv_unreadable"}
        ) from None

    items: List[PreviewItem] = []
    duplicates: List[Dict[str, Any]] = []
    ignored: List[Dict[str, Any]] = []
    ambiguities: List[Dict[str, Any]] = [
        {
            "code": "not_canonical",
            "message": "CSV não é fonte canônica do realizado: serve para conferência e não pode ser aplicado "
                       "como extrato. Use o OFX da mesma conta.",
            "item": None,
        }
    ]
    seen: Set[str] = set()
    for row in rows:
        description = str(row.get("description") or "").strip()
        occurred_on = _csv_date(row.get("date"))
        signed = _checked_amount(row.get("amount"))
        tx_type = row.get("type")
        # O parser do produto devolve o que ``float`` e ``pandas`` aceitarem:
        # "nan", "inf" e "NaT" passam por ele. A linha inválida não entra em
        # itens nem em totais; fica listada em ``ignored`` com o motivo.
        problem = None
        if occurred_on is None:
            problem = "Data inválida nesta linha do CSV."
        elif signed is None or money_str(abs(signed)) == "0.00":
            problem = "Valor inválido nesta linha do CSV (não numérico, zero ou fora do limite)."
        elif tx_type not in _CSV_TYPES:
            problem = "Tipo de lançamento desconhecido nesta linha do CSV."
        if problem is not None:
            ignored.append(
                {"occurred_on": occurred_on, "description": description,
                 # Só aparece quando é um número de verdade; senão, ausência.
                 "amount": money_str(abs(signed)) if signed is not None else None,
                 "fitid": None, "reason": problem, "nature": None}
            )
            continue
        # Mesma fórmula de chave que o produto usa para CSV, com o valor como o
        # parser entregou (é assim que o produto grava a chave).
        key = csv_dedup_key(row["date"], row["amount"], description, account_id, tx_type)
        category = row.get("category_name")
        item = PreviewItem(
            dedup_key=key,
            occurred_on=occurred_on,
            description=description,
            # ``PreviewItem.amount`` é sempre positivo: o sentido está em
            # ``type``. O CSV padrão do produto não tira o sinal, e um "-39,90"
            # de despesa somado como veio INVERTERIA o resultado líquido
            # (receita - (-despesa)).
            amount=money_str(abs(signed)),
            type=tx_type,
            fitid=None,
            nature=None,
            category_hint=str(category).strip() if category and str(category).strip() else None,
        )
        if key in existing_dedup_keys:
            duplicates.append(
                {"item": item.to_dict(), "reason": "Lançamento já existente nesta conta (mesma chave).",
                 "scope": "ledger"}
            )
            continue
        if key in seen:
            duplicates.append(
                {"item": item.to_dict(), "reason": "Lançamento idêntico repetido no próprio arquivo.",
                 "scope": "file"}
            )
            continue
        seen.add(key)
        items.append(item)
        if signed < 0 and tx_type == "income":
            # Saída com sinal negativo é a convenção dos bancos. RECEITA
            # negativa é contraditória (estorno? erro de exportação?): o item
            # é listado, mas pede conferência.
            ambiguities.append(
                {"code": "sign_conflict",
                 "message": "O valor desta linha é negativo, mas o tipo informado é receita. Confira o lançamento.",
                 "item": item.to_dict()}
            )
        if item.category_hint is None:
            ambiguities.append(
                {"code": "unclassified", "message": "Lançamento sem categoria definida.", "item": item.to_dict()}
            )
    if ignored:
        ambiguities.append(
            {"code": "invalid_rows",
             "message": "%d linha(s) do CSV foram ignoradas por terem data, valor ou tipo inválidos." % len(ignored),
             "item": None}
        )
    if not rows:
        ambiguities.append(
            {"code": "no_transactions", "message": "Nenhum lançamento foi reconhecido neste CSV.", "item": None}
        )

    period_start, period_end = _period(
        [item.occurred_on for item in items] + [entry["item"]["occurred_on"] for entry in duplicates]
    )
    return ImportPreview(
        artifact_id=record["artifact_id"],
        artifact_sha256=record["sha256"],
        filename=record["filename"],
        file_kind="csv",
        account_id=account_id,
        canonical=False,
        items=items,
        duplicates=duplicates,
        ambiguities=ambiguities,
        ignored=ignored,
        totals=_totals(
            items, currency=account["currency"], parsed=len(rows),
            duplicates=len(duplicates), ignored=len(ignored), ambiguities=len(ambiguities),
        ),
        institution=None,
        period_start=period_start,
        period_end=period_end,
        declared_balance=None,
    )


# ---------------------------------------------------------------------------
# Entrada pública.
# ---------------------------------------------------------------------------

def build_preview(pool, ctx: ExecutionContext, artifact_id: str, account_id: str, settings: AiSettings) -> ImportPreview:
    """Prévia de importação de um artefato para uma conta permitida.

    Erros: ``not_found`` (artefato ou conta fora do escopo, ou artefato
    expirado) e ``invalid_request`` (arquivo que é evidência, não extrato; CSV
    ilegível; OFX com valor não numérico ou fora do limite).
    """
    account_id = _require_account(ctx, account_id)
    record, content = read_artifact(pool, ctx, artifact_id, settings)
    kind = record["detected_kind"]
    if kind in EVIDENCE_KINDS:
        raise AiError(
            "invalid_request",
            "Este arquivo é uma evidência (comprovante), não um extrato: não há prévia de importação para ele.",
            details={"reason": "not_a_statement"},
        )
    account, existing_fitids, existing_dedup_keys = _load_account_and_ledger_keys(pool, ctx, account_id)

    if kind == "ofx":
        preview = _preview_ofx(ctx, record, content, account_id, account, existing_fitids, existing_dedup_keys)
    else:
        preview = _preview_csv(record, content, account_id, account, existing_dedup_keys)

    with scoped_tx(pool, ctx.tenant_id) as cursor:
        set_artifact_state(cursor, ctx, record["artifact_id"], "previewed")
        write_audit(
            cursor,
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.actor_id,
            event_type="ai.import.previewed",
            entity_type="ai_artifact",
            entity_id=record["artifact_id"],
            metadata={
                "financial_space_id": ctx.financial_space_id,
                "account_id": account_id,
                "sha256": record["sha256"],
                "file_kind": preview.file_kind,
                "canonical": preview.canonical,
                "items": len(preview.items),
                "duplicates": len(preview.duplicates),
                "ignored": len(preview.ignored),
                "ambiguities": len(preview.ambiguities),
                "run_id": ctx.run_id,
                "trace_id": ctx.trace_id,
            },
        )
    logger.info(
        "event=import_previewed artifact_id=%s kind=%s items=%d duplicates=%d ignored=%d ambiguities=%d",
        record["artifact_id"], preview.file_kind, len(preview.items), len(preview.duplicates),
        len(preview.ignored), len(preview.ambiguities),
    )
    return preview
