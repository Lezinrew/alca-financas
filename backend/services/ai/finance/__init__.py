"""Ferramentas financeiras da plataforma de IA (contrato, seções 5 e 9).

Módulos, do mais baixo para o mais alto:

* ``repository``: todo o SQL sobre as tabelas financeiras do PostgreSQL V2,
  sempre filtrado por tenant e espaço financeiro; a regra canônica do
  realizado (``source_file`` terminado em ``.ofx`` e status ``paid``).
* ``read``: consultas enumeradas que devolvem fatos com fonte.
* ``proposals``: prévias de alteração (baixa, importação, reversão), com
  chave de operação, hash do payload e versão dos alvos.
* ``operations``: aplicação idempotente de uma proposta em uma transação
  (efeito + auditoria + outbox) e consulta de estado.
* ``tools``: as cinco ferramentas ``finance.*`` para o ``ToolRegistry``.

Importar este pacote não abre conexão nem lê credenciais.
"""

from .tools import build_finance_tools

__all__ = ["build_finance_tools"]
