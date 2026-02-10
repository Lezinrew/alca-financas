#!/bin/bash

# Script para limpar o banco de dados MongoDB do Alça Finanças
# Uso: ./scripts/clear-database.sh

set -e

echo "🗑️  Limpando banco de dados do Alça Finanças"
echo ""

# Verifica se MongoDB está rodando
if ! mongosh --eval "db.version()" > /dev/null 2>&1; then
    echo "❌ MongoDB não está rodando!"
    echo "   Execute: ./scripts/start-mongodb.sh"
    exit 1
fi

# Confirma ação
read -p "⚠️  Tem certeza que deseja limpar TODOS os dados? (digite 'sim' para confirmar): " confirm

if [ "$confirm" != "sim" ]; then
    echo "❌ Operação cancelada"
    exit 0
fi

echo ""
echo "🧹 Limpando coleções..."

# Limpa todas as coleções
mongosh --quiet --eval "
use alca_financas

print('📊 Status antes da limpeza:');
db.getCollectionNames().forEach(function(col) {
    var count = db[col].countDocuments();
    print('  ' + col + ': ' + count + ' documentos');
});

print('');
print('🗑️  Removendo dados...');

db.getCollectionNames().forEach(function(col) {
    var result = db[col].deleteMany({});
    print('  ✓ ' + col + ': ' + result.deletedCount + ' documentos removidos');
});

print('');
print('📊 Status após limpeza:');
db.getCollectionNames().forEach(function(col) {
    var count = db[col].countDocuments();
    print('  ' + col + ': ' + count + ' documentos');
});
"

echo ""
echo "✅ Banco de dados limpo com sucesso!"
echo ""
echo "💡 Dicas:"
echo "   - Faça logout no frontend"
echo "   - Limpe o localStorage do navegador (F12 > Application > Storage > Clear)"
echo "   - Crie um novo usuário para começar do zero"
