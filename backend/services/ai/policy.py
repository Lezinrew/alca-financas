"""Perfis, modos de autonomia e autorizações permanentes (contrato, seção 3).

Regras centrais:

* ausência de grant nunca significa autorização; sem grant ativo com a
  capacidade, a ferramenta é negada;
* ``observe`` consulta e prepara prévias; ``assisted`` aplica após aprovação
  específica; ``delegated`` aplica sozinho dentro das restrições do grant;
* o executor revalida o grant imediatamente antes de cada efeito, dentro da
  mesma transação, com lock de linha (``lock_grant_for_effect``);
* grants só nascem e morrem pela API administrativa autenticada. Nenhuma
  ferramenta do modelo cria ou altera grants.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence

from .db import scoped_tx, write_audit
from .errors import AiError
from .types import ExecutionContext, Mode, to_decimal


CAPABILITIES = (
    "email.search_financial",
    "email.get_message",
    "email.download_attachment",
    "imports.preview",
    "finance.read",
    "finance.prepare_change",
    "finance.apply_change",
    "finance.operation_status",
    "finance.reverse_change",
    "rag.search_personal",
    "whatsapp.respond",
)

# Capacidades que produzem efeito financeiro durável.
EFFECT_CAPABILITIES = frozenset({"finance.apply_change", "finance.reverse_change"})

SOURCE_KINDS = ("email", "upload", "whatsapp", "manual")

_MODE_RANK = {Mode.OBSERVE.value: 0, Mode.ASSISTED.value: 1, Mode.DELEGATED.value: 2}

# ``account_ids::text[]``: o psycopg2 só converte ``uuid[]`` em lista quando há
# um conversor registrado na conexão; sem ele a coluna chega como o texto cru
# "{id1,id2}" e um ``frozenset`` desse texto vira um conjunto de caracteres.
_GRANT_COLUMNS = """
    id, tenant_id, financial_space_id, actor_user_id, granted_by_user_id, profile, mode,
    capabilities, account_ids::text[] AS account_ids, amount_limit, amount_unlimited, period_start, period_end,
    allowed_sources, policy_version, version, valid_from, valid_until,
    revoked_at, revocation_reason, created_at
"""


@dataclass(frozen=True)
class Grant:
    id: str
    tenant_id: str
    financial_space_id: str
    actor_user_id: str
    mode: str
    capabilities: FrozenSet[str]
    account_ids: Optional[FrozenSet[str]]
    amount_limit: Optional[Decimal]
    amount_unlimited: bool
    period_start: Optional[date]
    period_end: Optional[date]
    allowed_sources: Optional[FrozenSet[str]]
    policy_version: int
    version: int
    valid_from: datetime
    valid_until: Optional[datetime]
    revoked_at: Optional[datetime]

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Grant":
        return cls(
            id=str(row["id"]),
            tenant_id=str(row["tenant_id"]),
            financial_space_id=str(row["financial_space_id"]),
            actor_user_id=str(row["actor_user_id"]),
            mode=row["mode"],
            capabilities=frozenset(row["capabilities"] or ()),
            account_ids=frozenset(str(item) for item in row["account_ids"]) if row["account_ids"] else None,
            amount_limit=row["amount_limit"],
            amount_unlimited=bool(row["amount_unlimited"]),
            period_start=row["period_start"],
            period_end=row["period_end"],
            allowed_sources=frozenset(row["allowed_sources"]) if row["allowed_sources"] else None,
            policy_version=int(row["policy_version"]),
            version=int(row["version"]),
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
            revoked_at=row["revoked_at"],
        )

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "grant_id": self.id,
            "financial_space_id": self.financial_space_id,
            "actor_user_id": self.actor_user_id,
            "mode": self.mode,
            "capabilities": sorted(self.capabilities),
            "account_ids": sorted(self.account_ids) if self.account_ids else None,
            "amount_limit": str(self.amount_limit) if self.amount_limit is not None else None,
            "amount_unlimited": self.amount_unlimited,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "allowed_sources": sorted(self.allowed_sources) if self.allowed_sources else None,
            "policy_version": self.policy_version,
            "version": self.version,
            "valid_from": self.valid_from.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


_ACTIVE = "revoked_at IS NULL AND valid_from <= now() AND (valid_until IS NULL OR valid_until > now())"
# Condição SQL de grant ativo, para consultas de outros módulos.
ACTIVE_GRANT_SQL = _ACTIVE


def load_active_grants(cursor, ctx: ExecutionContext) -> List[Grant]:
    """Grants ativos do ator no espaço financeiro da execução."""
    cursor.execute(
        "SELECT " + _GRANT_COLUMNS + " FROM ai_grants "
        "WHERE tenant_id = %s AND financial_space_id = %s AND actor_user_id = %s AND " + _ACTIVE + " "
        "ORDER BY created_at, id",
        (ctx.tenant_id, ctx.financial_space_id, ctx.actor_id),
    )
    return [Grant.from_row(row) for row in cursor.fetchall()]


def best_grant(grants: Iterable[Grant], capability: str) -> Optional[Grant]:
    """Grant de maior autonomia que contém a capacidade."""
    candidates = [grant for grant in grants if capability in grant.capabilities]
    if not candidates:
        return None
    return max(candidates, key=lambda grant: _MODE_RANK[grant.mode])


def authorize(grants: Iterable[Grant], capability: str) -> Grant:
    """Confirma que a capacidade está autorizada. Não decide efeito."""
    grant = best_grant(grants, capability)
    if grant is None:
        raise AiError("capability_denied", "A capacidade %s não está autorizada." % capability)
    if capability in EFFECT_CAPABILITIES and grant.mode == Mode.OBSERVE.value:
        raise AiError("capability_denied", "O modo observe não aplica alterações.")
    return grant


def allowed_capabilities(grants: Iterable[Grant]) -> FrozenSet[str]:
    result = set()
    for grant in grants:
        for capability in grant.capabilities:
            if capability in EFFECT_CAPABILITIES and grant.mode == Mode.OBSERVE.value:
                continue
            result.add(capability)
    return frozenset(result)


@dataclass(frozen=True)
class EffectRequest:
    """Dados do efeito pretendido usados para checar as restrições do grant."""

    capability: str
    amount: Optional[Decimal] = None
    account_ids: Sequence[str] = ()
    source_kind: Optional[str] = None
    effect_date: Optional[date] = None


def grant_violation(grant: Grant, effect: EffectRequest) -> Optional[str]:
    """Motivo pelo qual o grant NÃO cobre o efeito, ou ``None`` se cobre."""
    if effect.capability not in grant.capabilities:
        return "capacidade fora do grant"
    if grant.account_ids is not None:
        # Grant restrito a contas só cobre efeito que diga em quais contas mexe.
        # Efeito sem conta identificada não pode passar por omissão.
        if not effect.account_ids:
            return "efeito sem conta identificada"
        outside = [account for account in effect.account_ids if str(account) not in grant.account_ids]
        if outside:
            return "conta fora do grant"
    if not grant.amount_unlimited:
        if grant.amount_limit is None:
            return "grant sem limite de valor definido"
        if effect.amount is None:
            return "valor do efeito desconhecido"
        if to_decimal(effect.amount) > grant.amount_limit:
            return "valor acima do limite do grant"
    if grant.period_start or grant.period_end:
        if effect.effect_date is None:
            return "data do efeito desconhecida"
        if grant.period_start and effect.effect_date < grant.period_start:
            return "data anterior ao período do grant"
        if grant.period_end and effect.effect_date > grant.period_end:
            return "data posterior ao período do grant"
    if grant.allowed_sources is not None:
        if not effect.source_kind or effect.source_kind not in grant.allowed_sources:
            return "origem fora do grant"
    return None


def delegated_grant_for(grants: Iterable[Grant], effect: EffectRequest) -> Optional[Grant]:
    """Grant delegado que cobre integralmente o efeito, se houver."""
    for grant in grants:
        if grant.mode == Mode.DELEGATED.value and grant_violation(grant, effect) is None:
            return grant
    return None


def lock_grant_for_effect(
    cursor,
    ctx: ExecutionContext,
    effect: EffectRequest,
    *,
    grant_id: Optional[str] = None,
    grant_version: Optional[int] = None,
) -> Grant:
    """Revalida a autorização imediatamente antes do efeito (mesma transação).

    Com ``grant_id`` (aprovação por grant delegado) trava e confere exatamente
    aquele grant e sua versão. Sem ``grant_id`` (aprovação específica) exige um
    grant ativo do ator, em modo assisted ou delegated, com a capacidade.

    O ``FOR SHARE`` faz uma revogação concorrente esperar o fim desta
    transação; depois dela, qualquer nova tentativa enxerga o grant revogado.
    """
    if effect.capability not in EFFECT_CAPABILITIES:
        raise ValueError("lock_grant_for_effect só se aplica a capacidades com efeito")

    if grant_id is not None:
        cursor.execute(
            "SELECT " + _GRANT_COLUMNS + ", (" + _ACTIVE + ") AS is_active FROM ai_grants "
            "WHERE id = %s AND tenant_id = %s FOR SHARE",
            (str(grant_id), ctx.tenant_id),
        )
        row = cursor.fetchone()
        if row is None or not row["is_active"]:
            raise AiError("capability_denied", "A autorização foi revogada ou expirou.")
        grant = Grant.from_row(row)
        if grant.actor_user_id != ctx.actor_id or grant.financial_space_id != ctx.financial_space_id:
            raise AiError("scope_denied")
        if grant_version is not None and grant.version != int(grant_version):
            raise AiError("capability_denied", "A autorização mudou depois da aprovação.")
        if grant.mode != Mode.DELEGATED.value:
            raise AiError("capability_denied", "A autorização não permite aplicação automática.")
        violation = grant_violation(grant, effect)
        if violation:
            raise AiError("capability_denied", "Efeito fora da autorização: %s." % violation)
        return grant

    cursor.execute(
        "SELECT " + _GRANT_COLUMNS + " FROM ai_grants "
        "WHERE tenant_id = %s AND financial_space_id = %s AND actor_user_id = %s "
        "AND %s = ANY(capabilities) AND mode IN ('assisted', 'delegated') AND " + _ACTIVE + " "
        "ORDER BY created_at, id FOR SHARE",
        (ctx.tenant_id, ctx.financial_space_id, ctx.actor_id, effect.capability),
    )
    rows = cursor.fetchall()
    if not rows:
        raise AiError("capability_denied", "Não há autorização ativa para aplicar alterações.")
    for row in rows:
        grant = Grant.from_row(row)
        # Em aprovação específica o titular já aprovou valor e data; do grant
        # valem as restrições de escopo (contas e origem).
        if grant.account_ids is not None and any(
            str(account) not in grant.account_ids for account in effect.account_ids
        ):
            continue
        if grant.allowed_sources is not None and effect.source_kind not in grant.allowed_sources:
            continue
        return grant
    raise AiError("capability_denied", "Efeito fora do escopo das autorizações ativas.")


# ---------------------------------------------------------------------------
# Administração de grants (somente pela API autenticada).
# ---------------------------------------------------------------------------

def space_role(cursor, ctx: ExecutionContext) -> Optional[str]:
    """Papel do ator no espaço financeiro do contexto, ou ``None`` se não é membro."""
    cursor.execute(
        """
        SELECT role FROM financial_space_members
        WHERE tenant_id = %s AND financial_space_id = %s AND user_id = %s
        """,
        (ctx.tenant_id, ctx.financial_space_id, ctx.actor_id),
    )
    row = cursor.fetchone()
    return row["role"] if row else None


def require_space_owner(cursor, ctx: ExecutionContext) -> None:
    """Exige que o ator seja o titular (``owner``) do espaço do contexto."""
    _require_space_owner(cursor, ctx.tenant_id, ctx.financial_space_id, ctx.actor_id)


def _require_space_owner(cursor, tenant_id: str, financial_space_id: str, user_id: str) -> None:
    cursor.execute(
        """
        SELECT role FROM financial_space_members
        WHERE tenant_id = %s AND financial_space_id = %s AND user_id = %s
        """,
        (tenant_id, financial_space_id, user_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise AiError("not_found", "Espaço financeiro não encontrado.")
    if row["role"] != "owner":
        raise AiError("capability_denied", "Somente o titular do espaço gerencia autorizações.")


def list_grants(pool, ctx: ExecutionContext, include_revoked: bool = False) -> List[Grant]:
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute(
            "SELECT " + _GRANT_COLUMNS + " FROM ai_grants "
            "WHERE tenant_id = %s AND financial_space_id = %s "
            + ("" if include_revoked else "AND revoked_at IS NULL ")
            + "ORDER BY created_at DESC, id",
            (ctx.tenant_id, ctx.financial_space_id),
        )
        return [Grant.from_row(row) for row in cursor.fetchall()]


def create_grant(
    pool,
    ctx: ExecutionContext,
    *,
    mode: str,
    capabilities: Sequence[str],
    actor_user_id: Optional[str] = None,
    account_ids: Optional[Sequence[str]] = None,
    amount_limit: Optional[Any] = None,
    amount_unlimited: bool = False,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    allowed_sources: Optional[Sequence[str]] = None,
    valid_until: Optional[datetime] = None,
) -> Grant:
    """Cria um grant no espaço do contexto. Quem cria é ``ctx.actor_id``."""
    if mode not in _MODE_RANK:
        raise AiError("invalid_request", "Modo de autonomia inválido.", details={"field": "mode"})
    capabilities = sorted(set(capabilities or ()))
    unknown = [item for item in capabilities if item not in CAPABILITIES]
    if not capabilities or unknown:
        raise AiError("invalid_request", "Lista de capacidades inválida.", details={"field": "capabilities"})
    if allowed_sources is not None:
        allowed_sources = sorted(set(allowed_sources))
        if not allowed_sources or any(item not in SOURCE_KINDS for item in allowed_sources):
            raise AiError("invalid_request", "Origens inválidas.", details={"field": "allowed_sources"})
    limit = None
    if amount_limit is not None:
        try:
            limit = to_decimal(amount_limit)
        except ValueError:
            raise AiError("invalid_request", "Limite de valor inválido.", details={"field": "amount_limit"})
        if limit <= 0:
            raise AiError("invalid_request", "Limite de valor inválido.", details={"field": "amount_limit"})
    if amount_unlimited and limit is not None:
        raise AiError("invalid_request", "Escolha entre limite de valor e valor ilimitado.")
    if mode == Mode.DELEGATED.value and not amount_unlimited and limit is None:
        raise AiError(
            "invalid_request",
            "No modo delegado, defina um limite de valor ou declare explicitamente que é ilimitado.",
            details={"field": "amount_limit"},
        )
    if period_start and period_end and period_end < period_start:
        raise AiError("invalid_request", "Período inválido.", details={"field": "period_end"})

    grantee = str(actor_user_id or ctx.actor_id)
    account_list = sorted({str(item) for item in account_ids}) if account_ids else None

    with scoped_tx(pool, ctx.tenant_id) as cursor:
        _require_space_owner(cursor, ctx.tenant_id, ctx.financial_space_id, ctx.actor_id)
        cursor.execute(
            """
            SELECT 1 FROM financial_space_members
            WHERE tenant_id = %s AND financial_space_id = %s AND user_id = %s
            """,
            (ctx.tenant_id, ctx.financial_space_id, grantee),
        )
        if cursor.fetchone() is None:
            raise AiError("invalid_request", "O usuário autorizado não participa deste espaço.")
        if account_list:
            cursor.execute(
                """
                SELECT count(*) AS total FROM financial_space_accounts
                WHERE tenant_id = %s AND financial_space_id = %s AND account_id = ANY(%s::uuid[])
                """,
                (ctx.tenant_id, ctx.financial_space_id, account_list),
            )
            if cursor.fetchone()["total"] != len(account_list):
                raise AiError("invalid_request", "Há contas fora deste espaço.", details={"field": "account_ids"})
        cursor.execute(
            "INSERT INTO ai_grants ("
            " tenant_id, financial_space_id, actor_user_id, granted_by_user_id, mode, capabilities,"
            " account_ids, amount_limit, amount_unlimited, period_start, period_end, allowed_sources,"
            " policy_version, valid_until"
            ") VALUES (%s, %s, %s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING " + _GRANT_COLUMNS,
            (
                ctx.tenant_id,
                ctx.financial_space_id,
                grantee,
                ctx.actor_id,
                mode,
                capabilities,
                account_list,
                limit,
                bool(amount_unlimited),
                period_start,
                period_end,
                allowed_sources,
                ctx.policy_version,
                valid_until,
            ),
        )
        grant = Grant.from_row(cursor.fetchone())
        write_audit(
            cursor,
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.actor_id,
            event_type="ai.grant.created",
            entity_type="ai_grant",
            entity_id=grant.id,
            metadata={
                "financial_space_id": ctx.financial_space_id,
                "grantee": grantee,
                "mode": mode,
                "capabilities": capabilities,
                "amount_limit": str(limit) if limit is not None else None,
                "amount_unlimited": bool(amount_unlimited),
                "version": grant.version,
                "policy_version": grant.policy_version,
                "trace_id": ctx.trace_id,
            },
        )
    return grant


def revoke_grant(pool, ctx: ExecutionContext, grant_id: str, reason: str) -> Grant:
    """Revoga um grant. Idempotente: revogar de novo devolve o mesmo estado."""
    reason = (reason or "").strip()
    if not reason:
        raise AiError("invalid_request", "Informe o motivo da revogação.", details={"field": "reason"})
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        _require_space_owner(cursor, ctx.tenant_id, ctx.financial_space_id, ctx.actor_id)
        cursor.execute(
            "SELECT " + _GRANT_COLUMNS + " FROM ai_grants "
            "WHERE id = %s AND tenant_id = %s AND financial_space_id = %s FOR UPDATE",
            (str(grant_id), ctx.tenant_id, ctx.financial_space_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise AiError("not_found", "Autorização não encontrada.")
        if row["revoked_at"] is not None:
            return Grant.from_row(row)
        cursor.execute(
            "UPDATE ai_grants SET revoked_at = now(), revoked_by_user_id = %s, revocation_reason = %s "
            "WHERE id = %s AND tenant_id = %s RETURNING " + _GRANT_COLUMNS,
            (ctx.actor_id, reason[:500], str(grant_id), ctx.tenant_id),
        )
        grant = Grant.from_row(cursor.fetchone())
        write_audit(
            cursor,
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.actor_id,
            event_type="ai.grant.revoked",
            entity_type="ai_grant",
            entity_id=grant.id,
            metadata={"reason": reason[:500], "version": grant.version, "trace_id": ctx.trace_id},
        )
    return grant
