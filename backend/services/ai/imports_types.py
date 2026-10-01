"""Formato normalizado de prévia de importação.

É a fronteira entre a geração da prévia (``services.ai.imports``) e a criação
de propostas (``services.ai.finance``). Valores são decimais em string; nunca
float. A prévia de OFX é produzida pelo importador determinístico existente
(``services.ofx_import.OfxImportPipeline``), sem lógica paralela.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PreviewItem:
    dedup_key: str
    occurred_on: str          # data local YYYY-MM-DD
    description: str
    amount: str               # decimal positivo em string; o sinal está em ``type``
    type: str                 # income | expense | transfer
    fitid: Optional[str] = None
    nature: Optional[str] = None
    category_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ImportPreview:
    artifact_id: str
    artifact_sha256: str
    filename: str
    file_kind: str            # ofx | csv
    account_id: str
    # Somente OFX é fonte canônica do realizado. CSV/PDF/imagem geram prévia ou
    # evidência, mas não podem ser aplicados como extrato.
    canonical: bool
    items: List[PreviewItem] = field(default_factory=list)
    # Cada duplicado: {"item": PreviewItem-dict, "reason": str, "scope": "file"|"ledger"}
    duplicates: List[Dict[str, Any]] = field(default_factory=list)
    # Cada ambiguidade: {"code": str, "message": str, "item": PreviewItem-dict | None}
    ambiguities: List[Dict[str, Any]] = field(default_factory=list)
    ignored: List[Dict[str, Any]] = field(default_factory=list)
    # Totais em string decimal: income, expense, transfer, net; contagens em int.
    totals: Dict[str, Any] = field(default_factory=dict)
    institution: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    declared_balance: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ImportPreview":
        data = dict(payload)
        data["items"] = [PreviewItem(**item) for item in data.get("items") or []]
        return cls(**data)
