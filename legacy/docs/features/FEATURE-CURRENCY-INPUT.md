# Feature: Currency Input Component (Mobills-style)

## Overview
Implementação de um campo de input formatado para valores monetários no estilo Mobills, que formata automaticamente os valores em tempo real conforme o usuário digita.

## Component: CurrencyInput

### Location
`/frontend/src/components/ui/CurrencyInput.tsx`

### Features
1. ✅ Formatação automática em tempo real (1234.56 → "1.234,56")
2. ✅ Permite apenas números e vírgula
3. ✅ Limita a 2 casas decimais
4. ✅ Seleciona todo o texto ao focar (melhor UX)
5. ✅ Formata completamente ao sair do campo (blur)
6. ✅ Suporta atributos de acessibilidade (`aria-invalid`, `inputMode="decimal"`)
7. ✅ Compatível com formulários existentes

### How It Works

#### 1. Display Value vs. Actual Value
```typescript
// O componente mantém dois valores:
displayValue: "1.234,56"  // O que o usuário vê
actualValue: "1234.56"    // O que é enviado para o parent (número puro)
```

#### 2. Formatting Logic
```typescript
// Formata: 1234.56 → "1.234,56"
const formatCurrency = (num: number | string): string => {
  return numValue.toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
};

// Desformata: "1.234,56" → "1234.56"
const unformatCurrency = (formatted: string): string => {
  const cleaned = formatted.replace(/\./g, '').replace(',', '.');
  return parseFloat(cleaned).toString();
};
```

#### 3. User Input Flow
```
Usuário digita "1234" → Display: "1234" → Parent recebe: "1234"
Usuário digita "," → Display: "1234," → Parent recebe: "1234"
Usuário digita "5" → Display: "1234,5" → Parent recebe: "1234.5"
Usuário digita "6" → Display: "1234,56" → Parent recebe: "1234.56"
Campo perde foco → Display: "1.234,56" → Parent recebe: "1234.56"
```

### Props Interface
```typescript
interface CurrencyInputProps {
  id?: string;                    // ID do input (para label)
  name: string;                   // Nome do campo (required)
  value: number | string;         // Valor controlado
  onChange: (e) => void;          // Handler de mudança
  placeholder?: string;           // Placeholder (default: "0,00")
  disabled?: boolean;             // Desabilitar input
  required?: boolean;             // Campo obrigatório
  className?: string;             // Classes CSS
  autoComplete?: string;          // Autocomplete hint
}
```

### Usage Example

#### Basic Usage
```tsx
import CurrencyInput from '../ui/CurrencyInput';

const [amount, setAmount] = useState('');

<CurrencyInput
  name="amount"
  value={amount}
  onChange={(e) => setAmount(e.target.value)}
  placeholder="0,00"
  required
/>
```

#### With Bootstrap Input Group
```tsx
<div className="input-group">
  <span className="input-group-text">R$</span>
  <CurrencyInput
    id="transaction-amount"
    name="amount"
    className="form-control"
    value={formData.amount}
    onChange={handleChange}
    placeholder="0,00"
    required
  />
</div>
```

## Integration

### TransactionForm.tsx
Substituído o input type="number" por CurrencyInput:

**Before:**
```tsx
<input
  type="number"
  name="amount"
  value={formData.amount}
  onChange={handleChange}
  step="0.01"
  min="0.01"
/>
```

**After:**
```tsx
<CurrencyInput
  name="amount"
  value={formData.amount}
  onChange={handleChange}
  placeholder="0,00"
/>
```

## Benefits

### User Experience
- ✅ Formatação visual imediata (como Mobills, Nubank, etc)
- ✅ Feedback visual claro do valor sendo digitado
- ✅ Seleciona tudo ao focar (fácil substituir valor)
- ✅ Previne entrada de valores inválidos
- ✅ `inputMode="decimal"` abre teclado numérico no mobile

### Developer Experience
- ✅ API simples e familiar (igual a input normal)
- ✅ Totalmente tipado (TypeScript)
- ✅ Compatível com formulários existentes
- ✅ Não quebra validações ou submissões

### Accessibility
- ✅ `aria-invalid="false"` - Para screen readers
- ✅ `inputMode="decimal"` - Otimizado para mobile
- ✅ Funciona com labels normais
- ✅ Mantém todos os atributos de acessibilidade

## Input Validation

### What's Allowed
- ✅ Números: `0-9`
- ✅ Vírgula: `,` (separador decimal)
- ✅ Máximo 2 casas decimais

### What's Blocked
- ❌ Letras
- ❌ Símbolos (exceto vírgula)
- ❌ Múltiplas vírgulas
- ❌ Mais de 2 casas decimais
- ❌ Valores negativos (use campo separado para tipo)

## Mobile Optimization
```tsx
inputMode="decimal"  // Mostra teclado numérico com vírgula/ponto
```

Isso garante que em dispositivos móveis o teclado correto seja exibido, facilitando a entrada de valores.

## Future Enhancements

### Possible Improvements
1. Suporte a prefixo customizável (€, $, £)
2. Suporte a sufixo (%, etc)
3. Min/max value validation
4. Highlight invalid values
5. Suporte a valores negativos (com sinal)
6. Animação de formatação

### Additional Components
- `PercentageInput` - Para porcentagens
- `NumberInput` - Para inteiros formatados (ex: 1.000.000)
- `PhoneInput` - Para telefones formatados

## Testing Checklist

- [ ] Digitar valores inteiros (ex: 100)
- [ ] Digitar valores decimais (ex: 100,50)
- [ ] Digitar valores com vírgula no final (ex: 100,)
- [ ] Testar blur (deve formatar completamente)
- [ ] Testar focus (deve selecionar tudo)
- [ ] Testar copiar/colar valores
- [ ] Testar no mobile (teclado decimal)
- [ ] Testar com screen reader
- [ ] Testar formulário submission
- [ ] Testar edição de transação existente

## Files Modified

### New Files
- `/frontend/src/components/ui/CurrencyInput.tsx` - Component implementation

### Modified Files
- `/frontend/src/components/transactions/TransactionForm.tsx`
  - Line 3: Import CurrencyInput
  - Lines 276-286: Replace number input with CurrencyInput

## Date
2025-11-16
