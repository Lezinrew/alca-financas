#!/usr/bin/env bash
set -euo pipefail

echo "==> Testando se o problema do botão 'Adicionar Categoria' foi resolvido"
echo

# Verificar se o backend está rodando
echo "1. Verificando backend (porta 8001)..."
if curl -s http://localhost:8001/api/health >/dev/null; then
    echo "   ✓ Backend OK"
else
    echo "   ✗ Backend não está rodando"
    exit 1
fi

# Verificar se o frontend está rodando
echo "2. Verificando frontend (porta 3000)..."
if curl -s http://localhost:3000 >/dev/null; then
    echo "   ✓ Frontend OK"
else
    echo "   ✗ Frontend não está rodando"
    exit 1
fi

# Testar login e obter token
echo "3. Testando login do usuário demo..."
LOGIN_RESPONSE=$(curl -s -H "Content-Type: application/json" -X POST -d '{"email":"demo@alca.fin","password":"demo123"}' http://localhost:8001/api/auth/login)
TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.token // empty')

if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
    echo "   ✓ Login OK - Token obtido"
else
    echo "   ✗ Falha no login"
    echo "   Resposta: $LOGIN_RESPONSE"
    exit 1
fi

# Testar listagem de categorias
echo "4. Testando listagem de categorias..."
CATEGORIES_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/categories)
CATEGORIES_COUNT=$(echo "$CATEGORIES_RESPONSE" | jq '. | length')

if [ "$CATEGORIES_COUNT" -gt 0 ]; then
    echo "   ✓ Categorias encontradas: $CATEGORIES_COUNT"
else
    echo "   ✗ Nenhuma categoria encontrada"
    exit 1
fi

# Testar criação de categoria
echo "5. Testando criação de categoria..."
CREATE_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -X POST -d '{"name":"Teste API","type":"expense","color":"#ff0000","icon":"star"}' http://localhost:8001/api/categories)
CREATED_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id // empty')

if [ -n "$CREATED_ID" ] && [ "$CREATED_ID" != "null" ]; then
    echo "   ✓ Categoria criada com sucesso (ID: $CREATED_ID)"
    
    # Limpar categoria de teste
    curl -s -H "Authorization: Bearer $TOKEN" -X DELETE "http://localhost:8001/api/categories/$CREATED_ID" >/dev/null
    echo "   ✓ Categoria de teste removida"
else
    echo "   ✗ Falha ao criar categoria"
    echo "   Resposta: $CREATE_RESPONSE"
    exit 1
fi

echo
echo "==> RESULTADO: API funcionando perfeitamente!"
echo
echo "Se o botão 'Adicionar Categoria' ainda estiver esmaecido no frontend:"
echo "1. Abra o DevTools do navegador (F12)"
echo "2. Vá para a aba Console"
echo "3. Tente clicar no botão 'Adicionar Categoria'"
echo "4. Verifique se há erros de rede ou JavaScript"
echo "5. Verifique se a URL da API está correta (deve ser http://localhost:8001/api)"
echo
echo "Para forçar o frontend a usar a URL correta:"
echo "1. Pare o frontend (Ctrl+C no terminal onde está rodando)"
echo "2. Execute: cd frontend && REACT_APP_BACKEND_URL=http://localhost:8001 npm run dev"
echo "3. Recarregue a página no navegador"
