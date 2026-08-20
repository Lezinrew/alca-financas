# Fluxo e Arquitetura de Importação OFX — AlcaHub

Este documento especifica o funcionamento técnico, regras de negócio e fluxo do pipeline de importação bancária e de cartões de crédito no AlcaHub (`alca-financas`).

---

## 1. Visão Geral do Pipeline

```
       [ Arquivo OFX ] (Upload via API / Interface)
              │
              ▼
┌─────────────────────────────┐
│ 1. Parser & Encoding        │  -> Força decodificação UTF-8 (ignora USASCII/1252 do header)
│    (parser.py)              │  -> Detecta conta pelo bloco (<STMTRS> vs <CCSTMTRS>)
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 2. Nature Classifier        │  -> Cartão: descarta rotativo, saldo anterior e pagamentos espelhados
│    (nature.py)              │  -> Conta: classifica CDB/RDB/Pix próprio como type='transfer'
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 3. Deduplicação Universal   │  -> build_dedup_key(...) com normalização NFKD e sem espaços duplos
│    (dedup.py)               │  -> Preserva FITIDs distintos no mesmo dia via fila FIFO
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 4. Categorização por Regras │  -> Consulta merchant_category_aliases do tenant
│    (categorizer.py)         │  -> Prioridade por maior termo (matchLen) + boundary regex
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 5. Normalizador de Lote     │  -> Preenche todas as chaves canônicas com None (elimina PGRST102)
│    (normalizer.py)          │
└─────────────┬───────────────┘
              │
              ├──► is_preview == True  ──► Retorna Relatório JSON (Dry-run, sem escrita)
              │
              └──► is_preview == False ──► Grava em `transactions` + `import_batches`
```

---

## 2. Detecção por Bloco XML (Sem Heurística de Nome de Arquivo)

O importador não depende de nomes de arquivo (que frequentemente sofrem sufixos como `(1)`, `(2)` pelo navegador). A detecção é 100% estrutural:

| Bloco OFX Identificado | Tipo de Conta | Comportamento |
|---|---|---|
| `<BANKMSGSRSV1><STMTRS>` | Conta Corrente | Fluxo de caixa: entradas, Pix, transferências, débito, tarifas. |
| `<CREDITCARDMSGSRSV1><CCSTMTRS>` | Cartão de Crédito | Fatura: compras a prazo, encargos e IOF. |

---

## 3. Matriz de Classificação de Natureza

### 3.1 Cartão de Crédito
| Lançamento no OFX | Natureza | Ação Executada |
|---|---|---|
| Compras em estabelecimentos | Despesa real | Lançada como `type = 'expense'`, classificada por categoria |
| `Multa por fatura atrasada`, `Juros...`, `IOF...` | Custo financeiro real | Lançada como `type = 'expense'` na categoria **Financeiro** |
| `Pagamento recebido` | Espelho de pagamento | **Ignorado** (o débito real já sai da conta corrente) |
| `Valor pendente do mês anterior`, `... (rotativo)` | Saldo rolado | **Ignorado** (evita duplicar despesas passadas) |

### 3.2 Conta Corrente
| Lançamento no OFX | Natureza | Ação Executada |
|---|---|---|
| Pix recebido de terceiros, Salário, Depósito | Receita real | Lançada como `type = 'income'` |
| Compras no débito, Boletos de serviços/moradia | Despesa real | Lançada como `type = 'expense'` |
| `Aplicacao RDB`, `Resgate RDB`, `CDB`, `Mesma titularidade` | Transferência interna | Lançada como `type = 'transfer'` (excluída dos totais de receita/despesa) |
| Pix para mesma titularidade (mesmo CPF) | Transferência interna | Lançada como `type = 'transfer'` |

---

## 4. Deduplicação Determinística (`build_dedup_key`)

A chave universal de deduplicação é calculada pela fórmula pura:

```
{data_iso}|{valor_com_sinal:.2f}|{slug_descricao}|{banco_ou_conta}|{fitid}
```

### Regras de Sanitização:
1. **Espaços Múltiplos:** `re.sub(r"\s+", "_", texto)` (nunca `.replace(" ", "_")`).
2. **Acentos:** Decomposição NFKD com remoção de combining diacritics.
3. **Caracteres Especiais:** Remoção de caracteres de largura zero (`\u200b`, `\u200c`, `\u200d`, `\ufeff`).
4. **Colisão de FITIDs:** Transações no mesmo dia com mesmo valor e descrição, mas com FITIDs distintos, recebem chaves distintas e são ambas importadas sem colisão.

---

## 5. Endpoints da API

### 5.1 Preview / Dry-run (`POST /api/transactions/import/preview`)
Executa todo o pipeline em memória e retorna estatísticas completas antes da gravação:
- `import_batch_id`
- Total lido × Transações válidas × Duplicatas ignoradas × Itens descartados
- Total de receita, despesa e transferências
- Lançamentos sem categoria (para criação de regras)
- Conciliação contra o `LEDGERBAL` do extrato.

### 5.2 Efetivação (`POST /api/transactions/import`)
Grava o lote atomicamente no Supabase com `import_batch_id`, atualiza o saldo da conta para transações pagas e registra auditoria em `import_batches`.

### 5.3 Rollback Atômico (`POST /api/transactions/import/rollback/<batch_id>`)
Permite reverter instantaneamente um lote inteiro importado por engano:
1. Localiza todas as transações com `import_batch_id = <batch_id>` do tenant.
2. Reverte o impacto no saldo de cada conta associada.
3. Exclui as transações.
4. Marca o lote como `rolled_back` na tabela `import_batches`.
