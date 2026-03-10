"""
FAQ: respostas fixas para perguntas comuns do produto.
Retorna resposta sem chamar OpenClaw.
"""
from typing import Optional

from chatbot.intent import normalize_for_intent

# Chaves normalizadas (lower, single spaces) -> resposta
FAQ_ENTRIES = {
    "como cadastrar despesa": (
        "Para **cadastrar uma despesa**:\n\n"
        "1. Acesse o menu **Transações**\n"
        "2. Clique em **Adicionar Transação**\n"
        "3. Selecione o tipo **Despesa**\n"
        "4. Preencha descrição, valor, categoria, data e conta\n"
        "5. Clique em **Salvar**\n\n"
        "Você também pode usar **Importar** para enviar várias transações de um arquivo CSV."
    ),
    "como editar transação": (
        "Para **editar uma transação**:\n\n"
        "1. Vá em **Transações** no menu\n"
        "2. Localize a transação na lista\n"
        "3. Clique nela (ou no ícone de editar)\n"
        "4. Altere os campos desejados\n"
        "5. Clique em **Salvar**"
    ),
    "como excluir transação": (
        "Para **excluir uma transação**:\n\n"
        "1. Acesse **Transações**\n"
        "2. Localize a transação\n"
        "3. Clique no ícone de excluir (lixeira) ou abra a transação e use **Excluir**\n"
        "4. Confirme a exclusão\n\n"
        "A exclusão é permanente. Para apenas ocultar, você pode editar o status."
    ),
    "como cadastrar conta": (
        "Para **cadastrar uma conta**:\n\n"
        "1. Acesse o menu **Contas**\n"
        "2. Clique em **Adicionar Conta** (ou **Nova Conta**)\n"
        "3. Preencha: nome, tipo (corrente, poupança, carteira, etc.), saldo inicial e opcionalmente instituição\n"
        "4. Clique em **Salvar**\n\n"
        "Depois você pode vincular transações a essa conta."
    ),
    "como criar transação": (
        "Para **criar uma transação**:\n\n"
        "1. Menu **Transações** → **Adicionar Transação**\n"
        "2. Escolha o tipo: **Receita** ou **Despesa**\n"
        "3. Preencha: descrição, valor, categoria, conta e data\n"
        "4. (Opcional) Configure parcelas ou recorrência\n"
        "5. **Salvar**"
    ),
    "como registrar receita": (
        "Para **registrar uma receita**:\n\n"
        "1. Vá em **Transações** → **Adicionar Transação**\n"
        "2. Selecione o tipo **Receita**\n"
        "3. Informe descrição, valor, categoria, conta e data\n"
        "4. Salve"
    ),
}


def get_faq_response(message: str) -> Optional[str]:
    """
    Retorna resposta do FAQ se a mensagem normalizada bater com alguma entrada
    (exato ou se a chave do FAQ estiver contida na mensagem).
    """
    normalized = normalize_for_intent(message)
    if not normalized:
        return None

    # Match exato
    if normalized in FAQ_ENTRIES:
        return FAQ_ENTRIES[normalized]

    # Match por contenção: alguma chave do FAQ está contida na mensagem
    for key, answer in FAQ_ENTRIES.items():
        if key in normalized or normalized in key:
            return answer

    return None
