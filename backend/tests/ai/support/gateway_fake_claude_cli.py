"""Executável simulado do Claude Code para os testes do adaptador.

Roda como subprocesso real: grava o que recebeu (argumentos, entrada padrão,
diretório e variáveis de cobrança presentes) e devolve a resposta programada.
"""

from __future__ import annotations

import json
import os
import sys
import time


def main() -> int:
    with open(os.environ["FAKE_CLAUDE_PLAN"], encoding="utf-8") as handle:
        plan = json.load(handle)
    if sys.argv[1:] == ["--version"]:
        print("0.0.0 (simulado)")
        return 0
    record = {
        "argv": sys.argv[1:],
        "stdin": sys.stdin.buffer.read().decode("utf-8"),
        "cwd_entries": sorted(os.listdir(os.getcwd())),
        "billing_env": sorted(name for name in os.environ if name.startswith("ANTHROPIC_")),
    }
    with open(plan["record"], "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    with open(plan["record"], encoding="utf-8") as handle:
        calls = sum(1 for _ in handle)
    replies = plan["replies"]
    reply = replies[min(calls, len(replies)) - 1]
    if reply.get("sleep"):
        time.sleep(reply["sleep"])
    output = reply["raw"] if "raw" in reply else json.dumps(reply["body"], ensure_ascii=False)
    sys.stdout.buffer.write(output.encode("utf-8"))
    return int(reply.get("exit", 0))


if __name__ == "__main__":
    sys.exit(main())
