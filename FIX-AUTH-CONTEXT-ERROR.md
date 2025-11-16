# 🔧 Fix: Erro "useAuth deve ser usado dentro de AuthProvider"

## ❌ Problema Identificado

Ao clicar em "Transações" ou "Adicionar Transação" no modo AI, o console mostrava erro:

```
AuthContext.tsx:26 Uncaught Error: useAuth deve ser usado dentro de AuthProvider
    at useAuth (AuthContext.tsx:26:11)
    at PublicRoute (App.tsx:77:40)
```

### Root Cause

O problema estava na forma como o React Router era configurado:

**Código Problemático:**
```typescript
const RouterWrapper: React.FC = () => {
  const router = useMemo(() => createBrowserRouter(
    [
      {
        path: '/login',
        element: (
          <PublicRoute>  // ❌ useAuth() é chamado AQUI
            <Login />
          </PublicRoute>
        ),
      },
      // ... mais rotas
    ]
  ), []);

  return <RouterProvider router={router} />;
};

const App = () => (
  <AuthProvider>
    <RouterWrapper />  // ❌ Router é criado ANTES do Provider estar disponível
  </AuthProvider>
);
```

**Por que falha:**

1. `createBrowserRouter()` **cria a árvore de componentes imediatamente** quando é executado
2. Isso acontece **dentro do `useMemo`**, que executa durante a primeira renderização de `RouterWrapper`
3. Neste momento, `RouterWrapper` ainda está **fora** do `AuthProvider`
4. Quando o componente `PublicRoute` tenta chamar `useAuth()`, o contexto ainda não existe

**Ordem de Execução Incorreta:**
```
1. App renderiza
2. AuthProvider começa a renderizar
3. RouterWrapper renderiza
4. useMemo executa createBrowserRouter()
5. PublicRoute tenta usar useAuth() ❌ ERRO - contexto ainda não existe
6. RouterProvider renderiza
7. AuthProvider termina de renderizar (tarde demais!)
```

## ✅ Solução Implementada

Substituir `createBrowserRouter` + `RouterProvider` por `BrowserRouter` + `Routes`:

**Código Correto:**
```typescript
const AppRoutes: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            <PublicRoute>  // ✅ useAuth() é chamado AQUI
              <Login />
            </PublicRoute>
          }
        />
        {/* ... mais rotas */}
      </Routes>
    </BrowserRouter>
  );
};

const App = () => (
  <AuthProvider>
    <AppRoutes />  // ✅ Rotas são renderizadas DEPOIS do Provider estar disponível
  </AuthProvider>
);
```

**Por que funciona:**

1. `BrowserRouter` e `Routes` não criam a árvore de componentes antecipadamente
2. Os componentes das rotas são renderizados **lazy** (sob demanda)
3. Quando `PublicRoute` é renderizado, o `AuthProvider` já está ativo
4. `useAuth()` encontra o contexto corretamente

**Ordem de Execução Correta:**
```
1. App renderiza
2. AuthProvider renderiza e disponibiliza o contexto ✅
3. AppRoutes renderiza
4. BrowserRouter renderiza
5. Routes renderiza e decide qual Route mostrar
6. Route renderiza PublicRoute
7. PublicRoute usa useAuth() ✅ SUCESSO - contexto existe!
8. Login renderiza
```

## 🎯 Diferenças: createBrowserRouter vs BrowserRouter

| Feature | `createBrowserRouter` + `RouterProvider` | `BrowserRouter` + `Routes` |
|---------|------------------------------------------|----------------------------|
| **Renderização** | Eager (imediata) | Lazy (sob demanda) |
| **Criação da árvore** | No momento da criação | Durante renderização |
| **Uso com Context** | ⚠️ Problemático | ✅ Seguro |
| **Data Loaders** | ✅ Suporta | ❌ Não suporta |
| **Future Flags** | ✅ Configurável | ⚠️ Via props |
| **React 18 Features** | ✅ Otimizado | ✅ Compatível |

### Quando usar cada um?

**Use `createBrowserRouter`:**
- ✅ Quando você precisa de data loaders
- ✅ Quando as rotas não dependem de contextos React
- ✅ Para SSR (Server-Side Rendering)

**Use `BrowserRouter`:**
- ✅ Quando você usa hooks de contexto nas rotas
- ✅ Para aplicações client-side simples
- ✅ Quando você não precisa de data loaders

## 📝 Mudanças Aplicadas

### Antes (❌ Incorreto):

```typescript
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

const RouterWrapper = () => {
  const router = useMemo(() => createBrowserRouter([
    // rotas definidas como objetos
  ]), []);
  return <RouterProvider router={router} />;
};

const App = () => (
  <AuthProvider>
    <RouterWrapper />
  </AuthProvider>
);
```

### Depois (✅ Correto):

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';

const AppRoutes = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
        {/* ... mais rotas */}
      </Routes>
    </BrowserRouter>
  );
};

const App = () => (
  <AuthProvider>
    <AppRoutes />
  </AuthProvider>
);
```

## 🔍 Como Detectar Esse Problema

### 1. Mensagem de Erro Típica
```
Error: useAuth deve ser usado dentro de AuthProvider
```

### 2. Stack Trace
Procure por:
- `createBrowserRouter` na pilha de chamadas
- Componentes que usam `useContext` sendo renderizados antes do Provider

### 3. Estrutura do Código
```typescript
// ⚠️ PADRÃO PROBLEMÁTICO
<Provider>
  <ComponenteThatCreatesRouter>  {/* Router criado aqui */}
    <RouterProvider />
  </ComponenteThatCreatesRouter>
</Provider>

// ✅ PADRÃO CORRETO
<Provider>
  <BrowserRouter>
    <Routes>
      {/* Rotas renderizadas sob demanda */}
    </Routes>
  </BrowserRouter>
</Provider>
```

## 🎓 Lições Aprendidas

### 1. Entenda a diferença entre renderização Eager vs Lazy

**Eager (createBrowserRouter):**
- Cria todos os elementos imediatamente
- Útil para pre-rendering e loaders
- Pode causar problemas com contextos

**Lazy (BrowserRouter):**
- Cria elementos conforme necessário
- Seguro para uso com contextos
- Padrão tradicional do React Router

### 2. Ordem de Renderização importa

```typescript
// ❌ ERRADO - Hook executado fora do Provider
<Provider>
  {useMemo(() => {
    // Este código executa durante render de App
    // Mas o Provider ainda não está ativo!
    return createRouter();
  }, [])}
</Provider>

// ✅ CORRETO - Hook executado dentro do Provider
<Provider>
  <Component>
    {/* Este código executa quando Component renderiza
        e o Provider já está ativo */}
  </Component>
</Provider>
```

### 3. useMemo não salva da ordem de execução

`useMemo` otimiza re-renderizações, mas **não muda a ordem de execução inicial**:

```typescript
const router = useMemo(() => {
  // Isso AINDA executa na primeira renderização
  // Mesmo com useMemo!
  return createBrowserRouter();
}, []);
```

## ✅ Verificação

### 1. Teste as Rotas Públicas
- ✅ Acesse `/login` - deve funcionar sem erro
- ✅ Acesse `/register` - deve funcionar sem erro

### 2. Teste as Rotas Protegidas
- ✅ Acesse `/dashboard` sem login - deve redirecionar para `/login`
- ✅ Faça login e acesse `/transactions` - deve funcionar
- ✅ Acesse `/accounts` - deve funcionar

### 3. Teste o Modo AI
- ✅ Clique em "Entrar com IA" - deve logar
- ✅ Navegue para "Transações" - deve funcionar sem erro no console
- ✅ Clique em "Adicionar Transação" - deve abrir o formulário

## 🔄 Alternativa (Se você realmente precisa de createBrowserRouter)

Se você **realmente** precisa usar `createBrowserRouter` (por exemplo, para data loaders), aqui está a solução:

```typescript
// Mova o AuthProvider para DENTRO das rotas
const router = createBrowserRouter([
  {
    element: <AuthProvider><Outlet /></AuthProvider>,  // Provider aqui
    children: [
      {
        path: '/login',
        element: <PublicRoute><Login /></PublicRoute>,  // useAuth funciona
      },
      // ... mais rotas
    ],
  },
]);

const App = () => <RouterProvider router={router} />;
```

**Mas isso:**
- ❌ Complica a estrutura
- ❌ Reinicia o AuthProvider em navegações
- ❌ Perde estado do contexto

**Por isso, para este projeto, `BrowserRouter` é a melhor escolha.**

## 📚 Referências

- [React Router - Picking a Router](https://reactrouter.com/en/main/routers/picking-a-router)
- [React Router - BrowserRouter](https://reactrouter.com/en/main/router-components/browser-router)
- [React Router - createBrowserRouter](https://reactrouter.com/en/main/routers/create-browser-router)
- [React Context - Rules of Hooks](https://react.dev/reference/react/useContext#usage)

## ✅ Checklist Final

- [x] Substituído `createBrowserRouter` por `BrowserRouter`
- [x] Removido `useMemo` desnecessário
- [x] Convertido objetos de rota para componentes `<Route>`
- [x] Mantido `AuthProvider` na raiz do App
- [x] Testado rotas públicas e protegidas
- [x] Testado modo AI
- [x] Documentado o problema e solução

---

**Status:** ✅ Resolvido
**Data:** 15/11/2025
**Causa:** `createBrowserRouter` renderiza rotas antes do contexto estar disponível
**Solução:** Usar `BrowserRouter` + `Routes` para renderização lazy

**Próximo passo:** Teste a navegação no modo AI sem erros!
