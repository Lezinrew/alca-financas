"""Cofre de credenciais do conector de e-mail.

O banco guarda só uma REFERÊNCIA (``credential_ref``, ex.: ``env:NOME``). O
valor é buscado aqui, no instante do uso, e segue apenas para o cabeçalho
``Authorization`` da chamada ao provedor. Ele nunca volta em resultado de
ferramenta, erro, log ou auditoria.

Por que um objeto ``Secret`` em vez de ``str``: uma string solta acaba em
``repr``, f-string, ``logging`` ou ``json.dumps`` sem que ninguém perceba. O
``Secret`` só entrega o valor por ``reveal()``, um nome fácil de procurar no
código, e não é serializável (``json_safe`` da plataforma o rejeita).
"""

from __future__ import annotations

import os
import re
from typing import Dict, Mapping, Optional

try:  # Python 3.8+
    from typing import Protocol
except ImportError:  # pragma: no cover
    Protocol = object  # type: ignore

from ..errors import AiError


# esquema:nome -- o nome nunca contém espaço nem se parece com um token longo
# em base64 colado por engano no lugar da referência.
_CREDENTIAL_REF = re.compile(r"^(?P<scheme>[a-z][a-z0-9_]{1,20}):(?P<name>[A-Za-z0-9_.\-/]{1,120})$")
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,100}$")

# Só variáveis com este prefixo podem ser usadas como credencial de e-mail.
# Sem isso, uma referência "env:DATABASE_URL" faria a aplicação enviar um
# segredo de outra finalidade como token para o servidor de e-mail.
ENV_PREFIX = "AI_EMAIL_CREDENTIAL_"


class Secret:
    """Valor sensível que não aparece em ``repr``, ``str`` nem em serialização."""

    __slots__ = ("_reveal",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("segredo vazio")
        # Fechamento em vez de atributo: ``vars()``/``__dict__`` e depuradores
        # que listam atributos não mostram o valor.
        object.__setattr__(self, "_reveal", lambda: value)

    def reveal(self) -> str:
        """Único ponto de saída do valor. Use só ao montar o cabeçalho HTTP."""
        return self._reveal()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Secret é imutável")

    def __repr__(self) -> str:
        return "Secret(***)"

    __str__ = __repr__

    def __format__(self, format_spec: str) -> str:
        return "Secret(***)"

    def __reduce__(self):
        raise TypeError("Secret não pode ser serializado")

    def __bool__(self) -> bool:
        return True


class CredentialStore(Protocol):
    """Protocolo do cofre: resolve uma referência em um ``Secret``."""

    def get(self, credential_ref: str) -> Secret:  # pragma: no cover - protocolo
        ...


def _unavailable() -> AiError:
    # Mensagem única para referência inválida, variável ausente ou vazia: quem
    # recebe o erro não precisa (nem deve) saber qual nome foi consultado.
    return AiError(
        "connector_unavailable",
        "A credencial da caixa de e-mail não está disponível. Reconecte a conta.",
        retryable=False,
    )


def validate_credential_ref(credential_ref: object) -> str:
    """Confere o formato ``esquema:nome``. Devolve a referência normalizada."""
    if not isinstance(credential_ref, str) or not _CREDENTIAL_REF.match(credential_ref.strip()):
        raise AiError(
            "invalid_request",
            "Referência de credencial inválida. Informe a referência do cofre, nunca o token.",
            details={"field": "credential_ref"},
        )
    return credential_ref.strip()


def credential_scheme(credential_ref: Optional[str]) -> Optional[str]:
    """Só o esquema (``env``), para auditoria e logs."""
    if not credential_ref:
        return None
    match = _CREDENTIAL_REF.match(credential_ref)
    return match.group("scheme") if match else None


class EnvCredentialStore:
    """Referências ``env:NOME`` lidas do ambiente no momento do uso.

    Ler a cada chamada (e não guardar em cache) faz a rotação ou remoção da
    variável valer imediatamente, sem reiniciar o processo.
    """

    def __init__(self, env: Optional[Mapping[str, str]] = None, prefix: str = ENV_PREFIX) -> None:
        self._env = env
        self._prefix = prefix

    def get(self, credential_ref: str) -> Secret:
        match = _CREDENTIAL_REF.match(credential_ref or "")
        if match is None or match.group("scheme") != "env":
            raise _unavailable()
        name = match.group("name")
        if not _ENV_NAME.match(name) or not name.startswith(self._prefix):
            raise _unavailable()
        env = os.environ if self._env is None else self._env
        value = (env.get(name) or "").strip()
        if not value:
            raise _unavailable()
        return Secret(value)

    def __repr__(self) -> str:
        return "EnvCredentialStore(prefix=%r)" % self._prefix


class InMemoryCredentialStore:
    """Cofre em memória para testes e desenvolvimento local."""

    def __init__(self, values: Optional[Mapping[str, str]] = None) -> None:
        self._values: Dict[str, Secret] = {}
        for credential_ref, value in (values or {}).items():
            self.put(credential_ref, value)

    def put(self, credential_ref: str, value: str) -> None:
        self._values[validate_credential_ref(credential_ref)] = Secret(value)

    def remove(self, credential_ref: str) -> None:
        self._values.pop(credential_ref, None)

    def get(self, credential_ref: str) -> Secret:
        secret = self._values.get(credential_ref or "")
        if secret is None:
            raise _unavailable()
        return secret

    def __repr__(self) -> str:
        return "InMemoryCredentialStore(refs=%d)" % len(self._values)
