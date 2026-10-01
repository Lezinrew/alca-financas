# RFC 0003: decisões de implementação da plataforma de IA

**Estado:** aceito para a implementação local; nada ativado em produção.
**Data:** 01/10/2026.
**Contrato:** [ai-platform-v1.md](../contracts/ai-platform-v1.md).
**Detalhamento:** [spec de implementação](../specs/ai-platform-implementation-v1.md).

Este RFC registra *por que* a implementação ficou como ficou. Cada decisão traz
a alternativa descartada e a consequência, para que possa ser revista com
consciência do que muda.

## Como ler: a ideia central em uma frase

O modelo de IA **propõe**; o backend **decide e executa**. Tudo que importa para
o dinheiro (quem é você, em qual espaço financeiro está, quanto vale uma soma,
se uma alteração já foi aplicada) é resolvido por código determinístico e por
índices do banco, não pelo texto que o modelo escreve.

## D1. Espaço financeiro como entidade própria, ligado por tabelas de vínculo

**Decisão.** Criar `financial_spaces` (`personal`, `family`, `business`) dentro
do tenant, com `financial_space_members`, `financial_space_accounts` e
`financial_space_payables`.

**Por quê.** O contrato exige `financial_space_id` em toda operação e separação
entre pessoal e negócio, mas o schema V2 (`0001_core.sql`) só tinha tenant.
Tabelas de vínculo não alteram nenhuma tabela da `0001`, que pertence a outra
frente, e a reversão é um `DROP` limpo.

**Alternativa descartada.** "Espaço = tenant" (proposta em
`docs/product/FATURAMENTO-NEGOCIO-PLANO.md`). Não exige schema novo, mas não
atende o caso "família dentro do mesmo tenant" e torna `financial_space_id`
redundante. As duas ideias convivem: tenants continuam isolados entre si e, dentro
de um tenant, os espaços separam os dados.

**Consequência.** Conta ou conta a pagar sem vínculo fica invisível para a IA.
Isso é intencional: ausência de vínculo nunca significa acesso amplo. Antes de
usar a IA é preciso vincular contas aos espaços.

## D2. Sessão V2 com CSRF na API da IA

**Decisão.** `/api/ai/v1` usa `require_v2_session` e exige `X-CSRF-Token` em todo
`POST`.

**Por quê.** As tabelas da IA vivem no PostgreSQL V2 e referenciam `users` e
`tenants` do V2. O contrato pede "sessão segura/CSRF" e o documento da auth V2 já
previa que as futuras rotas de escrita usariam esse mecanismo.

**Consequência.** O frontend atual autentica só pelo Supabase. Até o login V2
chegar ao frontend, a tela do operador não alcança a API real. Por isso a tela
fica atrás de `VITE_ENABLE_AI_OPERATOR` (desligada por padrão) e o cliente HTTP da
IA é uma instância separada: um `401` da IA nunca desloga o usuário do restante
do aplicativo.

**Alternativa descartada.** Aceitar o Bearer do Supabase. Exigiria mapear
identidades de dois bancos diferentes (os UUIDs não são os mesmos) e gravaria
efeitos financeiros em nome de um usuário que o V2 não conhece.

## D3. RLS com `FORCE`, mais filtro explícito no serviço

**Decisão.** Todas as tabelas novas têm RLS com `FORCE ROW LEVEL SECURITY` e
política `tenant_id = ai_current_tenant_id()`. O serviço abre cada transação com
`scoped_tx`, que define `app.tenant_id`. As consultas continuam filtrando por
`tenant_id` e espaço.

**Por quê.** São duas barreiras independentes: se uma consulta esquecer o
`WHERE`, o banco ainda devolve zero linhas de outro tenant.

**Limite importante.** Papéis `SUPERUSER` ou `BYPASSRLS` ignoram RLS. O compose
local de `infra/postgres-v2` usa o usuário criado pela imagem, que é superusuário.
Para o RLS valer é preciso criar um papel de aplicação comum. Os testes já rodam
com um papel assim.

**Fila.** O worker precisa descobrir execuções pendentes de qualquer tenant. Há
uma política própria, ativada por `app.ai_queue = 'on'`, que só enxerga linhas em
fila. Depois de assumir uma execução, o worker passa a operar no escopo do tenant
dono.

## D4. Gateway próprio, com adaptadores HTTP e sem SDKs de provedor

**Decisão.** Um gateway único escolhe a rota, aplica orçamento, timeout, circuito
e failover. Cada adaptador faz **uma** tentativa por chamada, usando `requests`.

**Por quê.** Os SDKs oficiais repetem chamadas por conta própria (dois retries
por padrão em Anthropic e OpenAI). O contrato exige um único dono do orçamento de
tentativas. Com HTTP direto, toda tentativa passa pelo contador do gateway.

**Consequência.** Os adaptadores externos (Anthropic, OpenAI-compatível,
OpenRouter) foram exercitados apenas contra servidores locais de teste. Nenhum foi
validado contra o provedor real: isso exige credenciais e autorização específica.

**OpenRouter.** Quando usado, a rota envia `provider.order` com um único
fornecedor, `allow_fallbacks: false` e `data_collection: "deny"`, e nunca envia
`models`. Assim o fornecedor efetivo fica fixado e o failover interno do agregador
fica desligado. A documentação não garante ausência de retry interno no mesmo
fornecedor; por isso o gateway também conta as tentativas informadas nos
metadados de roteamento.

## D5. API nativa do Ollama; ferramentas e saída estruturada em chamadas separadas

**Decisão.** Usar `POST /api/chat` nativo, com `stream: false`, `temperature: 0`,
semente fixa e `num_ctx` explícito.

**Por quê.** A API nativa aceita JSON Schema em `format`, permite `num_ctx` por
requisição e devolve métricas em nanossegundos. Enviar `tools` e `format` na
mesma chamada não é confiável (o `format` prevalece e as ferramentas são
ignoradas), então o laço de ferramentas roda sem `format` e a resposta final é
pedida em uma chamada só com `format`.

**`local_only` de verdade.** Falar com `localhost` não garante processamento
local: o Ollama pode encaminhar modelos remotos. Três controles: o servidor roda
com `OLLAMA_NO_CLOUD=1`; o registro rejeita nomes de modelo "cloud"; e a sonda
recusa modelo com `remote_host`/`remote_model`.

## D6. Registro de modelos em arquivo versionado, com estados

**Decisão.** `backend/services/ai/config/models.json` lista as rotas com
`candidate`, `approved` ou `suspended`. Só `approved` é selecionável, exceto em
desenvolvimento e benchmark (`AI_ALLOW_CANDIDATE_MODELS=true`).

**Por quê.** A homologação vira uma mudança revisável em arquivo: para aprovar um
modelo é preciso fixar tag e digest e apontar a evidência do benchmark. Tag
`latest` não pode ser aprovada.

**Estado atual.** Nenhuma rota está aprovada. As duas rotas locais são candidatas
e não há rota externa no arquivo padrão.

## D7. Efeito único: chave no backend, id determinístico e índice único

**Decisão.** A chave da operação é um SHA-256 de escopo + fonte + tipo +
identidade da ação. O id da operação é um UUIDv5 dessa chave. A linha em
`ai_operations`, o efeito financeiro, a auditoria e o outbox são gravados na
mesma transação, e `(tenant_id, operation_key)` é único.

**Por quê.** Se dois workers tentarem aplicar a mesma proposta, o segundo espera
o primeiro confirmar e então encontra a linha existente: devolve o resultado
anterior em vez de aplicar de novo. Como o id é calculável antes da chamada, um
timeout depois do commit é resolvido consultando o estado, sem reenvio às cegas.

**O que não se promete.** *Exactly-once* entre serviços externos. A entrega do
outbox pode se repetir; o consumidor deduplica por `dedup_key`.

## D8. Checkpoints por etapa; nada de prompt ou resposta bruta no banco

**Decisão.** Cada inferência e cada ferramenta é uma etapa com `step_key`
estável. Persiste-se a decisão estruturada (qual ferramenta, com quais
argumentos) e o resultado saneado; não o prompt nem a resposta bruta.

**Por quê.** Ao reiniciar o worker ou trocar de provedor, etapas concluídas são
reutilizadas. Guardar só a decisão estruturada cumpre a retenção do contrato e
ainda permite reconstruir a conversa.

## D9. E-mail atrás de uma interface própria; MCP por HTTP, sem SDK

**Decisão.** `EmailConnector` com três operações (`search`, `get_message`,
`download_attachment`). O conector MCP fala JSON-RPC por HTTP com `requests` e só
chama ferramentas de uma lista de permissão configurada.

**Por quê.** O SDK Python `mcp` 2.x exige `pydantic>=2.12`; o backend fixa
`2.5.2`. E a lista de permissão é a defesa real: servidores de e-mail costumam
anunciar ferramentas de enviar, apagar e rotular, que nunca devem ser chamadas.

**Achado que exige decisão do titular.** O servidor Gmail MCP oficial do Google,
como documentado em 01/10/2026, expõe busca e leitura, mas **não documenta
download de anexo**. As vias possíveis são: Gmail REST direto
(`users.messages.attachments.get`, escopo `gmail.readonly`), um servidor MCP de
terceiros em modo somente leitura, ou a leitura da mensagem em formato bruto
(MIME) pelo servidor do Google, ainda por provar. Nenhuma foi conectada.

**OAuth.** O banco guarda apenas `credential_ref`, uma referência ao cofre. O
fluxo de autorização com o provedor não foi implementado nesta entrega.

## D10. Prévia de importação reutiliza o importador do produto

**Decisão.** A prévia de OFX chama `OfxImportPipeline.process_file`, o mesmo
código usado em `/api/transactions/import`. Valores são convertidos para string
decimal na borda e os totais são recalculados em `Decimal`.

**Por quê.** O critério AC-02 pede a mesma prévia do importador determinístico.
Reutilizar o código torna isso verdadeiro por construção.

**Regra preservada.** Só OFX é fonte canônica do realizado. CSV gera prévia não
aplicável; PDF e imagem são evidência.

## D11. Grants por espaço, imutáveis

**Decisão.** Um grant vale para um espaço financeiro. Para mudar, revoga-se e
cria-se outro. Modo delegado exige decisão explícita de valor (teto ou
ilimitado).

**Por quê.** Imutabilidade simplifica a auditoria ("qual autorização valia quando
isto foi aplicado?") e a revalidação: a transação do efeito trava o grant e
confere a versão aprovada.

**Fase 1 preservada.** Proposta cuja única evidência é um comprovante nunca é
aplicada por grant. Sempre volta para revisão humana.

## D12. Resumo do modelo passa por uma guarda numérica

**Decisão.** Os fatos exibidos vêm das ferramentas. O texto do modelo só é aceito
se todo valor monetário citado existir nos fatos; caso contrário é trocado por um
resumo montado pelo backend, com aviso.

**Por quê.** Um modelo pode escrever um número errado com total confiança. A
guarda impede que esse número chegue ao titular como se fosse verdade.

## D13. Circuito de falhas em memória, por processo

**Decisão.** O estado do circuito fica na memória de cada processo.

**Consequência.** Com vários workers do gunicorn, cada um aprende as falhas
separadamente. É aceitável para o início, porque o orçamento de tentativas é
aplicado por execução; um circuito compartilhado (em banco ou Redis) é evolução
futura se a carga mostrar necessidade.

## D14. Hermes Agent não foi instalado

**Decisão.** Nenhuma instalação. O contrato o trata como executor opcional.

**Por quê.** Pela documentação oficial, ele vem com terminal, arquivos, navegador
e execução de código ligados por padrão, tem retries e fallback próprios (fora do
orçamento do gateway), guarda memória em `~/.hermes` sem isolamento por tenant e
exige contexto mínimo de 64 mil tokens. Ele também não aceita ferramentas vindas
da requisição: o registro do backend teria de ser exposto como servidor MCP.

**Hermes Agent não é a família de modelos Hermes.** O primeiro é um executor de
agentes; a segunda é um conjunto de modelos de linguagem. Um pode ser usado sem o
outro.

**O que seria preciso para avaliá-lo.** Expor o registro como servidor MCP com
contexto autenticado por execução; rodar só com o toolset MCP e provar em teste
que as ferramentas genéricas estão desligadas; contêiner sem volumes da VPS e sem
rota ao PostgreSQL; apontar o provedor do Hermes para o próprio gateway; repetir
os testes de isolamento.

## D15. RAG lexical, sem embeddings

**Decisão.** Busca por texto completo do PostgreSQL em português (`tsvector`),
com filtro por tenant, espaço e ACL antes da busca e de novo antes da entrega.

**Por quê.** Não exige modelo de embeddings nem extensão extra, e mantém o
conteúdo no mesmo banco, sob o mesmo RLS. Números financeiros nunca saem do RAG.

## D16. Validação de PDF depende de biblioteca opcional

**Decisão.** A contagem de páginas e a detecção de senha usam `pypdf` se estiver
instalado; sem ele, PDF é recusado.

**Por quê.** `pypdf` não está em `backend/requirements.txt`, e o CI usa Python
3.9. Adicionar uma dependência sem validar nessa versão poderia quebrar o
pipeline que antecede o deploy. Recusar é o padrão seguro; incluir a dependência
fica como decisão posterior.

## Consequências gerais

- O aplicativo financeiro e a Fase 1 de comprovantes não dependem de nenhum
  módulo novo. Com `AI_ENABLED=false` (padrão) nada muda.
- Há quatro flags independentes: IA, nuvem, e-mail e escrita. Todas nascem
  desligadas.
- A operação, a ativação e o rollback estão em
  [docs/runbooks/ai-platform.md](../runbooks/ai-platform.md).
