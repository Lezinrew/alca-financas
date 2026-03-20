# Feature: Excluir Planejamento

## Overview
Implementação da funcionalidade de exclusão de planejamentos mensais, permitindo que o usuário remova um orçamento definido para um determinado mês.

## Implementation

### Location
`/frontend/src/components/planning/Planning.tsx`

### New Function: handleDeletePlanning
```typescript
const handleDeletePlanning = () => {
  // Confirmação antes de excluir
  if (!window.confirm('Tem certeza que deseja excluir este planejamento? Esta ação não pode ser desfeita.')) {
    return;
  }

  try {
    // TODO: Excluir do backend quando a API estiver pronta
    localStorage.removeItem(`budget_${currentYear}_${currentMonth}`);
    setBudget(null);
    setError('');
  } catch (err: any) {
    console.error('Delete planning error:', err);
    setError('Erro ao excluir planejamento');
  }
};
```

### UI Changes

#### Delete Button
Adicionado botão "Excluir Planejamento" na parte inferior da tela, ao lado do botão "Editar Planejamento":

```tsx
<div className="flex justify-end gap-3">
  {/* Botão de Excluir */}
  <button
    type="button"
    onClick={handleDeletePlanning}
    className="px-4 py-2 bg-white dark:bg-slate-700 border border-red-300 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg font-medium transition-colors flex items-center gap-2"
  >
    <i className="bi bi-trash"></i>
    Excluir Planejamento
  </button>

  {/* Botão de Editar */}
  <button
    type="button"
    onClick={() => setShowForm(true)}
    className="px-4 py-2 bg-purple-600 hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
  >
    <i className="bi bi-pencil"></i>
    Editar Planejamento
  </button>
</div>
```

## Features

### 1. Confirmation Dialog
- ✅ Modal de confirmação nativo do browser (`window.confirm`)
- ✅ Mensagem clara: "Tem certeza que deseja excluir este planejamento? Esta ação não pode ser desfeita."
- ✅ Cancela operação se usuário clicar em "Cancelar"

### 2. Safe Deletion
- ✅ Remove apenas o planejamento do mês atual
- ✅ Não afeta planejamentos de outros meses
- ✅ Limpa o estado local (`setBudget(null)`)
- ✅ Remove do localStorage

### 3. Error Handling
- ✅ Try-catch para capturar erros
- ✅ Exibe mensagem de erro caso falhe
- ✅ Console.error para debug

### 4. Visual Feedback
- ✅ Botão vermelho com bordas vermelhas
- ✅ Ícone de lixeira
- ✅ Hover effect (fundo vermelho claro)
- ✅ Dark mode support

## User Flow

### Step by Step
1. Usuário navega para página de Planejamento
2. Usuário visualiza o planejamento do mês atual
3. Usuário clica no botão "Excluir Planejamento"
4. Modal de confirmação aparece
5. **Se usuário confirmar:**
   - Planejamento é removido do localStorage
   - Estado local é atualizado (`budget = null`)
   - Tela volta ao estado "Nenhum orçamento definido"
6. **Se usuário cancelar:**
   - Nada acontece, planejamento permanece

### After Deletion
Após excluir, o usuário verá a tela de "empty state" com as opções:
- "Definir Novo Planejamento"
- "Copiar Planejamento do Mês Anterior"

## Storage

### LocalStorage Key Pattern
```
budget_${year}_${month}
```

**Exemplos:**
- Janeiro 2025: `budget_2025_1`
- Dezembro 2024: `budget_2024_12`

### Deletion Impact
- ✅ Remove apenas o planejamento específico do mês
- ✅ Não afeta outros meses
- ✅ Pode ser recriado a qualquer momento

## Future Improvements

### Backend Integration
Quando a API de planejamentos estiver pronta:

```typescript
const handleDeletePlanning = async () => {
  if (!window.confirm('...')) return;

  try {
    setLoading(true);

    // Chamar API de exclusão
    await planningAPI.delete(budget.id);

    // Remover do localStorage como fallback
    localStorage.removeItem(`budget_${currentYear}_${currentMonth}`);

    setBudget(null);
    setError('');
  } catch (err: any) {
    console.error('Delete planning error:', err);
    setError(err.response?.data?.error || 'Erro ao excluir planejamento');
  } finally {
    setLoading(false);
  }
};
```

### Enhanced UX
1. **Loading State**: Mostrar spinner durante exclusão
2. **Toast Notification**: Mensagem de sucesso após exclusão
3. **Undo Action**: Opção de desfazer por alguns segundos
4. **Soft Delete**: Marcar como excluído ao invés de remover permanentemente
5. **Bulk Delete**: Excluir múltiplos planejamentos de uma vez
6. **Archive**: Arquivar ao invés de excluir

### Better Confirmation
Substituir `window.confirm` por modal customizado:

```tsx
<ConfirmDialog
  show={showDeleteConfirm}
  onConfirm={confirmDelete}
  onCancel={() => setShowDeleteConfirm(false)}
  title="Excluir Planejamento"
  message="Tem certeza que deseja excluir este planejamento? Esta ação não pode ser desfeita."
  confirmText="Excluir"
  confirmColor="danger"
/>
```

## Testing Checklist

- [ ] Clicar em "Excluir Planejamento"
- [ ] Verificar se modal de confirmação aparece
- [ ] Cancelar e verificar que planejamento permanece
- [ ] Confirmar e verificar que planejamento é removido
- [ ] Verificar se tela volta ao estado "empty"
- [ ] Verificar se localStorage foi limpo
- [ ] Testar em modo escuro (dark mode)
- [ ] Testar navegação para outro mês e voltar
- [ ] Criar novo planejamento após excluir
- [ ] Verificar que outros meses não são afetados

## Files Modified

### `/frontend/src/components/planning/Planning.tsx`
- **Lines 118-132**: Nova função `handleDeletePlanning`
- **Lines 428-445**: Adicionado botão "Excluir Planejamento" com ícone e estilos

## Visual Design

### Button Styles
```css
/* Light Mode */
background: white
border: red-300
text: red-600
hover background: red-50

/* Dark Mode */
background: slate-700
border: red-800
text: red-400
hover background: red-900/20
```

### Icon
- Bootstrap Icons: `bi-trash`
- Posicionamento: À esquerda do texto
- Spacing: `gap-2`

## Security Considerations

### Current Implementation
- ✅ Confirmação antes de excluir
- ✅ Ação não pode ser desfeita (mensagem clara)
- ✅ Erro handling básico

### Backend Requirements (Future)
- 🔒 Autenticação necessária
- 🔒 Validar que usuário é dono do planejamento
- 🔒 Soft delete no backend (não remover permanentemente)
- 🔒 Audit log da exclusão
- 🔒 Rate limiting para prevenir spam

## Date
2025-11-16
