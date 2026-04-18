import * as React from 'react';
import { cn } from '../../lib/utils';

export interface CurrencyInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value'> {
  value?: string;
  onValueChange?: (value: string | undefined, name?: string | null) => void;
  error?: string;
}

/**
 * CurrencyInput - Comportamento igual Nubank/Inter/Itaú
 *
 * ✅ Digite normalmente: "5000" ou "5000,50"
 * ✅ Formata automaticamente ao perder foco
 * ✅ Aceita vírgula ou ponto como decimal
 * ✅ Remove formatação ao focar (para edição fácil)
 *
 * Exemplos:
 * - Digitar "5000" → Exibe "5.000,00"
 * - Digitar "5000,50" → Exibe "5.000,50"
 * - Digitar "350.5" → Exibe "350,50"
 */
export const CurrencyInput = React.forwardRef<HTMLInputElement, CurrencyInputProps>(
  (
    {
      className,
      value,
      onValueChange,
      disabled,
      placeholder = '0,00',
      name,
      ...props
    },
    ref
  ) => {
    const [displayValue, setDisplayValue] = React.useState<string>('');
    const [isFocused, setIsFocused] = React.useState(false);
    const inputRef = React.useRef<HTMLInputElement>(null);

    // Combina refs (externa e interna)
    React.useImperativeHandle(ref, () => inputRef.current!);

    /**
     * Formata número para exibição: 5000.5 → "5.000,50"
     */
    const formatCurrency = (val: number): string => {
      const formatted = val.toLocaleString('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
      return formatted;
    };

    /**
     * Remove formatação: "5.000,50" → "5000.50"
     */
    const unformatCurrency = (formatted: string): string => {
      // Remove pontos de milhar e substitui vírgula por ponto
      return formatted.replace(/\./g, '').replace(',', '.');
    };

    /**
     * Parse string para número decimal
     */
    const parseToDecimal = (str: string): number => {
      if (!str || str.trim() === '') return 0;

      // Remove tudo exceto dígitos, vírgula e ponto
      let clean = str.replace(/[^\d,.-]/g, '');

      // Se tem vírgula e ponto, assume formato BR (1.000,50)
      if (clean.includes(',') && clean.includes('.')) {
        clean = clean.replace(/\./g, '').replace(',', '.');
      }
      // Se só tem vírgula, substitui por ponto
      else if (clean.includes(',')) {
        clean = clean.replace(',', '.');
      }
      // Se só tem ponto, mantém (pode ser milhar ou decimal)
      // Para desambiguar: se tem apenas 1 ponto e <= 2 dígitos após, é decimal
      // Caso contrário, remove pontos (milhares)
      else if (clean.includes('.')) {
        const parts = clean.split('.');
        if (parts.length === 2 && parts[1].length <= 2) {
          // É decimal: 100.50
          clean = clean;
        } else {
          // É milhar: 1.000 ou 1.000.000
          clean = clean.replace(/\./g, '');
        }
      }

      const num = parseFloat(clean);
      return isNaN(num) ? 0 : num;
    };

    /**
     * Converte número para string no formato BR para API: 5000.5 → "5000,50"
     */
    const toApiFormat = (num: number): string => {
      return num.toFixed(2).replace('.', ',');
    };

    // Sincroniza com prop value externa (quando componente pai atualiza)
    React.useEffect(() => {
      // Não atualizar se estiver focado (usuário editando)
      if (isFocused) return;

      if (value === undefined || value === null || value === '') {
        setDisplayValue('');
        return;
      }

      const num = parseToDecimal(value);
      setDisplayValue(formatCurrency(num));
    }, [value, isFocused]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const input = e.target.value;

      // Permite apenas dígitos, vírgula e ponto
      const filtered = input.replace(/[^\d,.-]/g, '');

      setDisplayValue(filtered);

      // Envia para o pai o valor parseado em formato BR
      const num = parseToDecimal(filtered);
      const apiValue = toApiFormat(num);
      onValueChange?.(apiValue, name);
    };

    const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(true);

      // Remove formatação para facilitar edição
      if (displayValue) {
        const unformatted = unformatCurrency(displayValue);
        setDisplayValue(unformatted);

        // Seleciona todo o texto após um micro-delay (para funcionar corretamente)
        setTimeout(() => {
          e.target.select();
        }, 10);
      }
    };

    const handleBlur = () => {
      setIsFocused(false);

      // Formata o valor ao perder foco
      if (displayValue) {
        const num = parseToDecimal(displayValue);
        const formatted = formatCurrency(num);
        setDisplayValue(formatted);

        // Envia valor final para o pai
        const apiValue = toApiFormat(num);
        onValueChange?.(apiValue, name);
      } else {
        // Se vazio, zera
        setDisplayValue('');
        onValueChange?.('0,00', name);
      }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      // Permite: números, backspace, delete, tab, escape, enter, setas
      const allowedKeys = [
        '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
        'Backspace', 'Delete', 'Tab', 'Escape', 'Enter',
        'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
        ',', '.'
      ];

      // Permite Ctrl/Cmd + A/C/V/X (select all, copy, paste, cut)
      if ((e.ctrlKey || e.metaKey) && ['a', 'c', 'v', 'x'].includes(e.key.toLowerCase())) {
        return;
      }

      if (!allowedKeys.includes(e.key)) {
        e.preventDefault();
      }
    };

    return (
      <input
        {...props}
        ref={inputRef}
        type="text"
        name={name}
        value={displayValue}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        inputMode="decimal"
        autoComplete="off"
        className={cn(
          'native-input-themed flex h-10 w-full rounded-md px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          isFocused && 'ring-2 ring-ring ring-offset-2',
          className
        )}
      />
    );
  }
);

CurrencyInput.displayName = 'CurrencyInput';

export default CurrencyInput;
