# Validação de leitura com Ollama real — 01/10/2026

**Decisão:** candidato `qwen2.5-coder:14b` reprovado para a fatia de leitura
financeira no perfil local descrito abaixo. Não promover a rota para `approved`.

## Escopo e critérios

Oito perguntas sintéticas em português sobre o realizado pessoal de outubro de
2026, pelo caminho login V2 real → POST `/api/ai/v1/runs` → worker → gateway →
Ollama real → GET da execução. PostgreSQL real descartável, papel sem
superusuário e RLS ativo. Nenhum `app.py`, dotenv, banco existente ou dado real.

Para passar, cada pergunta deve executar `finance.read`, devolver receitas
`1000.30`, despesas `100.30` e saldo `900.00`, conferidos por SQL NUMERIC
independente, e apresentar fontes para todos os fatos. O cenário inclui valores
grandes que devem ficar de fora: manual/CSV, legado, pendente, setembro, negócio
e outro tenant. Exige também auditoria sem cópia do pedido, nove transações do
tenant preservadas e ausência de avisos na resposta.

Isso é um teste da fatia de leitura, não o benchmark geral de 30 casos do
[contrato, seção 13](../contracts/ai-platform-v1.md). Documentos, ataques,
concorrência e outros modelos não foram homologados.

## Ambiente e perfil

- Windows, Python 3.11.9, Ollama 0.22.0.
- RAM física: aproximadamente 31,5 GiB; RTX 4070 Laptop, 8 GiB de VRAM.
- Modelo já instalado, sem download; digest
  `9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849`.
- Servidor próprio em `127.0.0.1:11435`, `OLLAMA_NO_CLOUD=1`.
- Registro temporário de uma rota `candidate`; somente leitura, cloud, e-mail
  e escrita desligados. `allow_candidate_models=True` apenas no laboratório.
- `num_ctx=4096`, `seed=7`, temperatura zero, `num_gpu=32`, `num_batch=64`,
  `use_mmap=True`, `keep_alive=5m`, concorrência de uma execução.
- Flash attention desligado, cache KV `f16`, `GGML_CUDA_NO_PINNED=1`.
  `num_gpu`, `num_batch` e `use_mmap` são exclusivos do adaptador de medição do
  teste; o adaptador de produção permanece intacto.
- `/api/ps` amostrado: `size=10028412928`, `size_vram=6466519040`, contexto 4096.
  Amostra do processo de inferência: working set de aproximadamente 9,48 GB;
  servidor aproximadamente 0,22 GB. VRAM observada: 6474 MiB. Não são limites
  garantidos nem medição contínua de pico.

## Resultado e diagnóstico

Na bateria inicial, **0/8 passaram**: todas as execuções terminaram como
`completed`, mas sem etapa `finance.read`, fatos ou fontes. O status da execução
isoladamente não comprova a resposta financeira.

A bateria confirmatória também teve **0/8**, nenhuma chamada nativa e nenhum
fato ou fonte. Mediana **12,883 s**, p95 por nearest rank **15,329 s** (somente
oito amostras, modelo aquecido); primeira consulta a frio no perfil funcional
**40,187 s**. Duas inferências por pergunta, custo de API zero. Em todos os casos,
as nove transações do tenant foram preservadas, os eventos `ai.run.created` e
`ai.run.finished` estavam presentes e não continham o pedido.

Um diagnóstico adicional da primeira pergunta encontrou a intenção da
ferramenta em `message.content` como JSON com chaves `name` e `arguments`,
`finish_reason=stop` e nenhuma chamada nativa. O gateway recusou esse JSON como
resposta final; na tentativa de correção o modelo devolveu `summary_pt_br`, ainda
sem consultar a ferramenta. Não converter texto livre em chamada de ferramenta.

Uma tentativa de tornar a instrução de leitura mais explícita também falhou na
primeira pergunta. A alteração de prompt foi revertida; seu hash foi comparado
com a cópia anterior e permanece idêntico.

Antes do perfil funcional, houve falhas reais de carregamento: falta de memória
para buffers CPU/CUDA e falha de compilação PTX no caminho flash attention.
O sistema respondeu `model_unavailable` em vez de assumir valores financeiros.
A opção `GGML_CUDA_NO_PINNED` e seu fallback para buffer CPU foram conferidos no
[código da versão instalada](https://github.com/ollama/ollama/blob/v0.22.0/ml/backend/ggml/ggml/src/ggml-cuda/ggml-cuda.cu#L1150).

O resumo JSON da bateria confirmatória fica em
`ai-ollama-read-2026-10-01.json`. Ele contém somente dados fictícios, métricas e
checagens; não guarda prompts nem respostas brutas. Os valores esperados não
chegaram a ser calculados por ferramenta: não declarar acerto de cálculo.

Os `case-NN.json` individuais ficaram exclusivamente fora do repositório em
`C:\Users\lezin\AppData\Local\Temp\alca-ollama-read-990e6f00be234f889ec50555d5676022\confirmed`.
Além de métricas, contêm estado, modelo, chaves do formato JSON, nomes de
ferramentas (vazios), etapas com horários e metadados de auditoria. Fatos e fontes
estão vazios. Não contêm prompts, respostas brutas, credenciais ou dados reais.
Por conterem metadados além de métricas/fatos, não foram copiados para o
repositório e não devem ser commitados. Nenhum commit foi realizado.

## Repetição e limpeza

Teste: `backend/tests/ai/test_ai_ollama_local_read.py`. Por padrão, os oito casos
são pulados; só chamam o modelo com configuração explícita. Inicie um servidor
local de laboratório com o perfil acima e, em PowerShell na pasta `backend`:

```powershell
$env:AI_REAL_OLLAMA_URL = 'http://127.0.0.1:11435'
$env:AI_REAL_OLLAMA_MODEL = 'qwen2.5-coder:14b'
$env:AI_REAL_OLLAMA_DIGEST = '9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849'
$env:AI_REAL_OLLAMA_REPORT_DIR = Join-Path $env:TEMP ('alca-ai-read-' + [guid]::NewGuid().ToString('N'))
Remove-Item Env:AI_TEST_PG_ADMIN_URL -ErrorAction SilentlyContinue
python -m pytest -c tests/ai/pytest.ini tests/ai/test_ai_ollama_local_read.py -s --tb=short
```

O fixture destrói apenas o banco de teste criado pela sessão no encerramento
normal. Encerre apenas a instância Ollama criada para o laboratório. Os modelos
instalados são preservados. Registro temporário não é usado pelo app.
Nesta execução, a instância criada e seu processo de inferência foram encerrados;
não há listener do laboratório na porta 11435. Os bancos das baterias concluídas
foram destruídos pelo fixture. A reprovação foi registrada em `evidence` da rota
`local-qwen25-coder-14b`, mantendo `state=candidate` e `approved_purposes=[]`.

Verificação final: testes existentes de API vertical e registro de modelos
passaram; os oito casos reais são pulados quando não há opt-in. Sintaxe Python
3.9 e `git diff --check` passaram. Não foi reexecutada a suíte inteira de 982
testes; código de produção e prompt ficaram intactos, exceto a evidência e nota
da rota no registro. Sem commit, push, deploy ou ativação.

Próximo trabalho: avaliar outra rota local com chamadas nativas de ferramentas
ou corrigir a integração com uma especificação própria e novos testes de
fronteira. Não ativar o candidato reprovado nem aceitar texto como comando para
fazer o teste passar. PostgreSQL 17 com extensões reais e desempenho da VPS
continuam pendentes.

## Rodadas seguintes (mesmo dia, mesmas oito perguntas e critérios)

| Rota | Modelo | Resultado | Tempo por pergunta |
|---|---|---|---|
| `local-qwen25-coder-14b` (reexecução pelo titular) | `qwen2.5-coder:14b` | 0/8 — nenhuma chamada de `finance.read` | 10–40 s |
| `plano-claude` (assinatura, `test_ai_claude_plan_read.py`) | `claude-sonnet-5-5` | 8/8 | 8–53 s |
| `local-qwen25-7b` | `qwen2.5:7b` (Q4_K_M, digest `845dbda0ea48…697e`) | 7/8 | 3–12 s |

`qwen2.5:7b`: em todos os casos houve uma chamada nativa de `finance.read`,
nenhuma gravação (9 lançamentos antes e depois) e nenhum aviso. Nos sete casos
aprovados os fatos bateram com o banco (entradas 1000.30, saídas 100.30,
líquido 900.00, ruído excluído). Caso 4 ("Quanto entrou e quanto saiu... pelo
extrato OFX pago?"): o modelo escolheu `spending_by_category` e respondeu só a
saída (100.30, correta), sem as entradas — reprovado pelo critério, que não foi
afrouxado. O download pelo `ollama pull` falhou por IPv6 (conexão encerrada pelo
registro); os blobs foram obtidos por IPv4 e conferidos por sha256 contra o
manifesto.

Nenhuma rota foi aprovada: todas seguem `candidate`. Oito perguntas não
substituem o benchmark de 30 casos.
