# 🔧 Fix: Erro ao Clicar em "Nova Conta"

## ❌ Problema Identificado

Ao clicar no botão "Nova Conta", o frontend exibia erro no console:

```
Load accounts error: SyntaxError: Unexpected token '<', "<!doctype "... is not valid JSON
```

### Root Cause

O componente `Accounts.tsx` estava usando `process.env.REACT_APP_BACKEND_URL` que é **undefined** no Vite.

Como a variável estava `undefined`, a requisição era feita para uma URL inválida, que retornava HTML ao invés de JSON.

## ✅ Solução Implementada

### 1. Corrigido `Accounts.tsx`

Substituído todas as ocorrências de `process.env.REACT_APP_BACKEND_URL` por `import.meta.env.VITE_API_URL`:

**Antes:**
```typescript
const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/accounts`, {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
  }
});
```

**Depois:**
```typescript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const response = await fetch(`${API_URL}/api/accounts`, {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
  }
});
```

### 2. Corrigido `Reports.tsx`

Mesmo problema no componente de relatórios:

**Antes:**
```typescript
const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/reports/overview?${params}`, {
```

**Depois:**
```typescript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const response = await fetch(`${API_URL}/api/reports/overview?${params}`, {
```

### 3. Atualizado Fallback em `api.ts`

Mudado o fallback de porta 5000 para 8001:

```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL || process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
```

## 🎯 Por Que Isso Aconteceu?

### Vite vs Create React App

| Framework | Variável de Ambiente | Acesso no Código |
|-----------|---------------------|------------------|
| Create React App | `REACT_APP_*` | `process.env.REACT_APP_*` |
| **Vite** | `VITE_*` | `import.meta.env.VITE_*` |

O projeto usa **Vite**, mas alguns componentes ainda tinham referências ao padrão do CRA.

### Sintomas do Problema

1. ✅ `src/utils/api.ts` estava correto (usando `import.meta.env.VITE_API_URL`)
2. ❌ `src/components/accounts/Accounts.tsx` usava `process.env.REACT_APP_BACKEND_URL`
3. ❌ `src/components/reports/Reports.tsx` usava `process.env.REACT_APP_BACKEND_URL`

Como essas variáveis eram `undefined`, as requisições falhavam.

## ✅ Arquivos Corrigidos

```
✅ frontend/src/components/accounts/Accounts.tsx
   - loadAccounts()
   - handleDeleteAccount()
   - handleFormSubmit()

✅ frontend/src/components/reports/Reports.tsx
   - loadReportData()

✅ frontend/src/utils/api.ts
   - Fallback atualizado para porta 8001
```

## 🔍 Como Detectar Esse Problema

### 1. Console do Browser
```javascript
// Se retornar undefined, é o problema
console.log(process.env.REACT_APP_BACKEND_URL)  // undefined

// Deve usar:
console.log(import.meta.env.VITE_API_URL)  // http://localhost:8001
```

### 2. Network Tab
- Requisições indo para URL inválida ou localhost sem porta
- Resposta em HTML ao invés de JSON

### 3. Grep no código
```bash
# Encontrar usos incorretos
grep -r "process.env.REACT_APP" frontend/src/

# Deve usar:
grep -r "import.meta.env.VITE_" frontend/src/
```

## 🔄 Padrão Correto para Vite

### Para usar variáveis de ambiente no Vite:

**1. Definir no `.env`:**
```bash
VITE_API_URL=http://localhost:8001
```

**2. Acessar no código:**
```typescript
const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001';
```

**3. TypeScript (opcional):**
```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

## ✅ Verificação

### 1. Verificar arquivo .env
```bash
cat frontend/.env
# Deve mostrar: VITE_API_URL=http://localhost:8001
```

### 2. Testar no browser console
```javascript
console.log(import.meta.env.VITE_API_URL)
// Deve retornar: http://localhost:8001
```

### 3. Testar funcionalidade
1. ✅ Acesse http://localhost:3000
2. ✅ Clique em "Contas" no menu
3. ✅ Clique em "Nova Conta"
4. ✅ Formulário deve abrir sem erros no console

## 📊 Status dos Componentes

| Componente | Status | API URL |
|-----------|--------|---------|
| Dashboard | ✅ OK | Usa `api.ts` (correto) |
| Transações | ✅ OK | Usa `api.ts` (correto) |
| Categorias | ✅ OK | Usa `api.ts` (correto) |
| **Contas** | ✅ CORRIGIDO | Agora usa `VITE_API_URL` |
| **Relatórios** | ✅ CORRIGIDO | Agora usa `VITE_API_URL` |
| Perfil | ✅ OK | Usa `api.ts` (correto) |
| Auth | ✅ OK | Usa `api.ts` (correto) |

## 🎓 Lição Aprendida

### Sempre use a instância centralizada do Axios

O projeto já tem uma instância configurada em `src/utils/api.ts` com todas as configurações corretas:

- ✅ Lê `VITE_API_URL` corretamente
- ✅ Adiciona token automaticamente
- ✅ Trata erros de autenticação
- ✅ Interceptors configurados

**Ao invés de:**
```typescript
const response = await fetch(`${import.meta.env.VITE_API_URL}/api/accounts`, {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
  }
});
```

**Prefira:**
```typescript
import api from '../../utils/api';

const response = await api.get('/accounts');
// Token já é adicionado automaticamente!
```

## 🔒 Próximos Passos (Opcional)

### Refatorar para usar API centralizada

Ao invés de `fetch` manual, usar a instância `api` do Axios:

```typescript
// Accounts.tsx - Refactor futuro
import api from '../../utils/api';

const loadAccounts = async () => {
  try {
    setLoading(true);
    const { data } = await api.get('/accounts');
    setAccounts(data);
  } catch (err) {
    setError('Erro ao carregar contas');
  } finally {
    setLoading(false);
  }
};
```

Isso eliminaria a necessidade de:
- ❌ Repetir configuração de URL em cada componente
- ❌ Adicionar token manualmente
- ❌ Tratar erros de autenticação em cada componente

## ✅ Checklist Final

- [x] `Accounts.tsx` corrigido para usar `VITE_API_URL`
- [x] `Reports.tsx` corrigido para usar `VITE_API_URL`
- [x] `api.ts` atualizado com fallback correto (porta 8001)
- [x] Todas as referências a `REACT_APP_BACKEND_URL` removidas dos componentes
- [x] `.env` configurado com `VITE_API_URL=http://localhost:8001`
- [x] Documentado o problema e solução

---

**Status:** ✅ Resolvido
**Data:** 15/11/2025
**Causa:** Uso incorreto de variável de ambiente (CRA vs Vite)
**Solução:** Substituir `process.env.REACT_APP_*` por `import.meta.env.VITE_*`

**Próximo passo:** Teste a funcionalidade de contas no navegador!
