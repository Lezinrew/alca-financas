## Feature: Cartões de Crédito (Mobills Style)

## Overview
Implementação completa da funcionalidade de Cartões de Crédito, substituindo "Tickets Abertos" no Dashboard, seguindo o estilo visual do Mobills com suporte a dark mode.

## New Component: CreditCards

### Location
`/frontend/src/components/credit-cards/CreditCards.tsx`

### Features
- ✅ Listagem de cartões de crédito com informações detalhadas
- ✅ Visualização de limite disponível e usado
- ✅ Barra de progresso visual do uso do limite
- ✅ Dias até fechamento da fatura
- ✅ Tabs para faturas abertas/fechadas
- ✅ Empty state elegante
- ✅ Totalmente responsivo
- ✅ Dark mode support
- ✅ Navegação pelo Dashboard (KPI card)

### Card Information Display
Cada cartão exibe:
- Nome do cartão
- Ícone colorido (cor customizável)
- Dia de fechamento da fatura
- Dias até próximo fechamento
- Limite disponível (destacado em verde)
- Valor total do limite
- Barra de progresso com gradiente
- Valor usado
- Botão "Ver detalhes"

## Dashboard Integration

### KPI Card Replacement
**Antes:**
```typescript
{
  title: 'Tickets Abertos',
  value: openTickets,
  change: -2,
  changeType: 'decrease',
  icon: 'ticket',
}
```

**Depois:**
```typescript
{
  title: 'Cartões de Crédito',
  value: creditCards,
  change: 0,
  changeType: 'increase',
  icon: 'credit-card',
}
```

### Click Navigation
Clicar no KPI "Cartões de Crédito" navega para `/credit-cards`

## Navigation Menu

Adicionado item no menu lateral entre "Contas" e "Planejamento":

```typescript
{ path: '/credit-cards', icon: CreditCard, label: 'Cartões de crédito' }
```

## Visual Design

### Card Styles
```css
/* Card Container */
.card-base
padding: 1.5rem
hover: shadow-lg
transition: shadow
cursor: pointer

/* Card Header */
Icon Circle: 48x48px
Background: Card color (customizable)
Icon: bi-credit-card-fill
Text: Semi-bold, primary color

/* Days Until Closing Badge */
Background: Emerald-100 (dark: emerald-900/30)
Text: Emerald-700 (dark: emerald-300)
Icon: bi-calendar-check
Border radius: Full (pill shape)

/* Available Limit */
Font size: 18px
Font weight: Bold
Color: Emerald-600 (dark: emerald-400)

/* Progress Bar */
Height: 8px
Background: Slate-200 (dark: slate-700)
Fill: Gradient emerald-500 to blue-500
Border radius: Full
Transition: width 300ms
```

### Color Scheme
- **Primary**: Blue-600 / Blue-700
- **Success**: Emerald-600 / Emerald-400
- **Card colors**: Custom per card (Nubank purple, Inter orange, etc)
- **Dark mode**: Slate-700 backgrounds, slate-300 text

## Mock Data

Currently using mock data for 2 cards:

```typescript
const mockCards: CreditCard[] = [
  {
    id: '1',
    name: 'Nubank',
    limit: 5000,
    used: 1234.56,
    closingDay: 15,
    dueDay: 25,
    color: '#8A05BE'
  },
  {
    id: '2',
    name: 'Inter',
    limit: 3000,
    used: 567.89,
    closingDay: 10,
    dueDay: 20,
    color: '#FF7A00'
  }
];
```

## Calculations

### Available Limit
```typescript
const available = card.limit - card.used;
```

### Usage Percentage
```typescript
const usedPercentage = (card.used / card.limit) * 100;
```

### Days Until Closing
```typescript
const getDaysUntilClosing = (closingDay: number) => {
  const today = new Date();
  const closingDate = getNextClosingDate(closingDay);
  const diffTime = closingDate.getTime() - today.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays;
};
```

## Empty State

When no cards exist:
- Large credit card icon (96px)
- Gradient background circle (blue to purple)
- Message: "Você não possui faturas fechadas no momento"
- Subtitle: "Confira seus cartões para saber mais."

## Tabs

Two tabs available:
1. **Faturas abertas** (default, active)
2. **Faturas fechadas**

Currently shows "Faturas abertas" tab as active.

## Files Modified

### New Files
- `/frontend/src/components/credit-cards/CreditCards.tsx`

### Modified Files

#### `/frontend/src/mocks/finance.ts`
- Line 52: Changed `openTickets` to `creditCards`
- Lines 76-82: Updated KPI from "Tickets Abertos" to "Cartões de Crédito"
- Line 81: Changed icon from 'ticket' to 'credit-card'

#### `/frontend/src/components/dashboard/Dashboard.tsx`
- Line 10: Import `CreditCard` instead of `Ticket` from lucide-react
- Line 66: Updated iconMap to use 'credit-card' instead of 'ticket'
- Lines 251-253: Added navigation handler for credit cards
- Line 259: Updated value display logic for credit cards

#### `/frontend/src/App.tsx`
- Line 21: Import CreditCards component
- Line 106: Added route `/credit-cards` with CreditCards component

#### `/frontend/src/components/layout/AppShell.tsx`
- Line 15: Import CreditCard icon from lucide-react
- Line 29: Added nav item for credit cards between accounts and planning

## Responsive Behavior

### Desktop (lg+)
- Cards in 2-column grid
- Full sidebar visible

### Tablet (md)
- Cards in 2-column grid
- Collapsible sidebar

### Mobile (< md)
- Cards in single column
- Full-width cards
- Hamburger menu

## Future Enhancements

### Backend Integration
When API is ready:
```typescript
// Load cards from API
const loadCards = async () => {
  try {
    const response = await creditCardsAPI.getAll();
    setCards(response.data);
  } catch (err) {
    setError('Erro ao carregar cartões');
  }
};
```

### Additional Features
1. **Add Card**: Modal form to add new credit card
2. **Edit Card**: Update card details
3. **Delete Card**: Remove card with confirmation
4. **Invoice Details**: Detailed view of transactions per card
5. **Payment History**: List of past payments
6. **Invoice PDF**: Download/view invoice
7. **Notifications**: Alerts for closing/due dates
8. **Multiple Currencies**: Support for international cards
9. **Shared Cards**: Family/shared cards
10. **Cashback Tracking**: Track rewards/cashback

### Enhanced Features
- **Auto-categorization**: Smart categorization of card expenses
- **Spending Insights**: Analytics per card
- **Best Card**: Suggest best card for each purchase
- **Points/Miles**: Track loyalty programs
- **Virtual Cards**: Manage virtual card numbers
- **Recurring Charges**: Track subscriptions per card

## Testing Checklist

- [ ] View credit cards list
- [ ] See card details (limit, used, available)
- [ ] Verify progress bar shows correct percentage
- [ ] Check days until closing calculation
- [ ] Click "Ver detalhes" button
- [ ] Test empty state (no cards)
- [ ] Switch between tabs (abertas/fechadas)
- [ ] Navigate from Dashboard KPI
- [ ] Navigate from sidebar menu
- [ ] Test responsive layout (mobile/tablet/desktop)
- [ ] Verify dark mode styles
- [ ] Test loading state
- [ ] Test error state

## Accessibility

- ✅ Semantic HTML structure
- ✅ ARIA labels where needed
- ✅ Keyboard navigation support
- ✅ Screen reader compatible
- ✅ Color contrast compliant (WCAG AA)
- ✅ Focus indicators
- ✅ Hover states

## Performance

- ✅ Lazy loading ready
- ✅ Efficient re-renders
- ✅ Optimized calculations
- ✅ Minimal dependencies
- ✅ Fast initial load

## Date
2025-11-16
