# Feature: Formulário de Despesa de Cartão de Crédito (Mobills Style)

## Overview
Implementação do formulário para adicionar despesas em cartões de crédito, seguindo fielmente o design do Mobills com todos os campos e funcionalidades.

## New Component: CreditCardExpenseForm

### Location
`/frontend/src/components/credit-cards/CreditCardExpenseForm.tsx`

### Features
- ✅ Campo de valor com formatação monetária (CurrencyInput)
- ✅ Seleção rápida de data (Hoje, Ontem, Outros)
- ✅ Campo de descrição
- ✅ Seletor de categoria (apenas despesas)
- ✅ Exibição do cartão selecionado
- ✅ Data de vencimento da fatura
- ✅ Toggle "Ignorar transação"
- ✅ Seção expansível "Mais detalhes"
  - Tags
  - Observação
  - Despesa fixa (toggle)
  - Parcelado (toggle)
  - Número de parcelas (quando parcelado)
- ✅ Validações de formulário
- ✅ Loading states
- ✅ Error handling
- ✅ Dark mode support

## Form Fields

### Main Fields

#### 1. Valor (Amount)
```tsx
<CurrencyInput
  name="amount"
  placeholder="0,00"
  required
/>
```
- Large input com formatação automática
- Prefixo "R$"
- Sufixo com seletor de moeda (BRL)
- Estilo: texto grande, azul, negrito

#### 2. Data (Date)
```tsx
<div className="btn-group">
  <input type="radio" id="date-today" value="today" />
  <label>Hoje</label>

  <input type="radio" id="date-yesterday" value="yesterday" />
  <label>Ontem</label>

  <input type="radio" id="date-other" value="other" />
  <label>Outros...</label>
</div>
```
- Botões de seleção rápida (Hoje, Ontem, Outros)
- Input de data aparece quando "Outros" é selecionado

#### 3. Descrição (Description)
```tsx
<input
  type="text"
  name="description"
  placeholder="Digite a descrição"
/>
```

#### 4. Categoria (Category)
```tsx
<select name="category_id" required>
  <option value="">Selecionar categoria</option>
  {expenseCategories.map(cat => (
    <option value={cat.id}>{cat.name}</option>
  ))}
</select>
```
- Apenas categorias do tipo "expense"

#### 5. Cartão de Crédito (Credit Card)
```tsx
<div className="p-3 bg-light rounded">
  <div className="d-flex align-items-center gap-3">
    <div style={{ backgroundColor: card.color }}>
      <i className="bi bi-credit-card-fill"></i>
    </div>
    <div>
      <div>{card.name}</div>
      <div>Fecha dia {card.closingDay}</div>
    </div>
  </div>
</div>
```
- Read-only display
- Mostra ícone colorido, nome e dia de fechamento

#### 6. Data de Vencimento (Due Date)
```tsx
<select>
  <option>15 de dez de 2025</option>
</select>
```
- Calculado automaticamente baseado no dia de fechamento

#### 7. Ignorar Transação (Ignore Transaction)
```tsx
<div className="form-check form-switch">
  <input
    type="checkbox"
    name="ignore_transaction"
  />
  <label>Ignorar transação</label>
</div>
```

### More Details Section

#### 8. Tags
```tsx
<input
  type="text"
  name="tags"
  placeholder="Digite as tags"
/>
```

#### 9. Observação (Observation)
```tsx
<textarea
  name="observation"
  rows={3}
  placeholder="Digite a observação"
/>
```

#### 10. Despesa Fixa (Fixed Expense)
```tsx
<div className="form-check form-switch">
  <input
    type="checkbox"
    name="is_fixed"
  />
  <label>Despesa fixa</label>
</div>
```

#### 11. Parcelado (Installment)
```tsx
<div className="form-check form-switch">
  <input
    type="checkbox"
    name="is_installment"
  />
  <label>Parcelado</label>
</div>
```

#### 12. Número de Parcelas (Installments Count)
```tsx
{formData.is_installment && (
  <div className="input-group">
    <input
      type="number"
      name="installments"
      min="2"
      max="60"
      value={formData.installments}
    />
    <span>vezes</span>
  </div>
)}
```
- Só aparece quando "Parcelado" está ativado
- Mínimo: 2 parcelas
- Máximo: 60 parcelas
- Default: 2 parcelas

## Validation Rules

### Required Fields
1. ✅ Valor (amount) - deve ser > 0
2. ✅ Categoria (category_id)

### Error Messages
- "Deve ter um valor diferente de 0" - quando amount <= 0
- "Categoria é obrigatória" - quando category_id vazio

## User Interaction Flow

### Opening Modal
1. Usuário clica em qualquer card de cartão na listagem
2. Modal abre com formulário vazio
3. Cartão selecionado é exibido (read-only)

### Filling Form
1. Usuário digita valor (formatação automática)
2. Seleciona data (Hoje/Ontem/Outros)
3. Digita descrição (opcional)
4. Seleciona categoria (obrigatório)
5. Opcionalmente:
   - Marca "Ignorar transação"
   - Expande "Mais detalhes"
   - Preenche campos adicionais

### Submitting
1. Clica em "Salvar"
2. Validações são executadas
3. Se válido:
   - Loading state ativa
   - Dados salvos
   - Modal fecha
   - Lista de cartões recarrega
4. Se inválido:
   - Erro exibido no topo do formulário
   - Foco no campo com erro

### Buttons
- **Salvar e criar nova**: Salva e mantém modal aberto
- **Salvar**: Salva e fecha modal

## State Management

```typescript
const [formData, setFormData] = useState({
  amount: '',
  date: 'today',
  description: '',
  category_id: '',
  card_id: card.id,
  tags: '',
  observation: '',
  is_fixed: false,
  is_installment: false,
  installments: 2,
  ignore_transaction: false
});

const [loading, setLoading] = useState(false);
const [error, setError] = useState('');
const [showMoreDetails, setShowMoreDetails] = useState(false);
```

## Integration with CreditCards Component

### Modified Files

#### `/frontend/src/components/credit-cards/CreditCards.tsx`

**Imports:**
```typescript
import CreditCardExpenseForm from './CreditCardExpenseForm';
import { categoriesAPI } from '../../utils/api';
```

**New State:**
```typescript
const [categories, setCategories] = useState([]);
const [showExpenseForm, setShowExpenseForm] = useState(false);
const [selectedCard, setSelectedCard] = useState<CreditCard | null>(null);
```

**New Methods:**
```typescript
const handleCardClick = (card: CreditCard) => {
  setSelectedCard(card);
  setShowExpenseForm(true);
};

const handleExpenseSubmit = async (expenseData: any) => {
  // TODO: Save to backend
  console.log('Despesa salva:', expenseData);

  setShowExpenseForm(false);
  setSelectedCard(null);
  await loadCards();
};
```

**Card Click Handler:**
```typescript
<div
  className="card-base cursor-pointer"
  onClick={() => handleCardClick(card)}
>
```

**Modal Render:**
```tsx
{showExpenseForm && selectedCard && (
  <CreditCardExpenseForm
    show={showExpenseForm}
    onHide={() => {
      setShowExpenseForm(false);
      setSelectedCard(null);
    }}
    onSubmit={handleExpenseSubmit}
    card={selectedCard}
    categories={categories}
  />
)}
```

## Styling

### Modal Styles
```css
/* Value Input - Large and Primary */
.form-control-lg {
  font-size: 2rem;
  font-weight: bold;
  color: var(--primary);
  border: 0;
  border-bottom: 1px solid;
  border-radius: 0;
  padding-left: 0;
}

/* Date Button Group */
.btn-group {
  width: 100%;
}

.btn-outline-primary {
  flex: 1;
}

/* Card Display */
.bg-light.dark\:bg-slate-700 {
  padding: 1rem;
  border-radius: 0.5rem;
}

/* More Details Toggle */
.btn-link {
  color: var(--primary);
  text-decoration: none;
  padding: 0;
}

/* Form Switches */
.form-check-switch {
  padding-left: 2.5em;
}

.form-check-input {
  width: 3em;
  height: 1.5em;
}
```

### Dark Mode Support
All fields respect dark mode:
- Inputs: `dark:bg-slate-700`
- Text: `dark:text-white`
- Borders: `dark:border-slate-600`
- Backgrounds: `dark:bg-slate-800`

## Backend Integration (Future)

When API is ready:

```typescript
const handleExpenseSubmit = async (expenseData: any) => {
  try {
    // POST /api/credit-cards/:cardId/expenses
    await creditCardExpensesAPI.create(expenseData.card_id, {
      amount: expenseData.amount,
      date: expenseData.date,
      description: expenseData.description,
      category_id: expenseData.category_id,
      tags: expenseData.tags,
      observation: expenseData.observation,
      is_fixed: expenseData.is_fixed,
      is_installment: expenseData.is_installment,
      installments: expenseData.installments,
      ignore_transaction: expenseData.ignore_transaction
    });

    setShowExpenseForm(false);
    await loadCards();
  } catch (err) {
    throw err;
  }
};
```

## Testing Checklist

### Basic Flow
- [ ] Click on credit card
- [ ] Modal opens
- [ ] Card information is displayed correctly
- [ ] Enter amount (test currency formatting)
- [ ] Select date (Hoje, Ontem, Outros)
- [ ] Enter description
- [ ] Select category
- [ ] Submit form
- [ ] Modal closes
- [ ] Card list reloads

### Validations
- [ ] Submit without amount (error)
- [ ] Submit with amount = 0 (error)
- [ ] Submit without category (error)
- [ ] Error message displays correctly
- [ ] Error clears on field change

### More Details Section
- [ ] Click "Mais detalhes"
- [ ] Section expands
- [ ] Enter tags
- [ ] Enter observation
- [ ] Toggle "Despesa fixa"
- [ ] Toggle "Parcelado"
- [ ] Installments field appears
- [ ] Change installments number
- [ ] Click "Menos detalhes"
- [ ] Section collapses

### Date Selection
- [ ] Select "Hoje" - correct date
- [ ] Select "Ontem" - yesterday's date
- [ ] Select "Outros" - date picker appears
- [ ] Pick custom date

### UI/UX
- [ ] Loading state on submit
- [ ] "Salvar" button works
- [ ] "Salvar e criar nova" button works
- [ ] Close button (X) works
- [ ] Click outside doesn't close (by design)
- [ ] ESC key closes modal
- [ ] Tab navigation works
- [ ] Dark mode renders correctly

### Responsive
- [ ] Mobile view (320px+)
- [ ] Tablet view (768px+)
- [ ] Desktop view (1024px+)

## Accessibility

- ✅ All inputs have labels
- ✅ Required fields marked
- ✅ Error messages associated with fields
- ✅ Keyboard navigation
- ✅ Focus management
- ✅ ARIA labels where needed
- ✅ Screen reader compatible

## Performance

- ✅ Lazy loading (only loads when card clicked)
- ✅ Categories loaded once
- ✅ Efficient re-renders
- ✅ Form state managed locally
- ✅ Validation on submit only

## Date
2025-11-16
