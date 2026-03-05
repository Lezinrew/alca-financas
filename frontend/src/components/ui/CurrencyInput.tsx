import * as React from 'react';
import { cn } from '../../lib/utils';

export interface CurrencyInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value'> {
  value?: string;
  onValueChange?: (value: string | undefined, name?: string | null) => void;
  error?: string;
}

/**
 * CurrencyInput com comportamento de banco brasileiro
 * - Digita da direita para esquerda (últimos 2 dígitos são centavos)
 * - Exemplo: digitar "1000" = R$ 10,00
 * - Exemplo: digitar "123456" = R$ 1.234,56
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
    // Estado interno para controlar o valor em centavos
    const [centavos, setCentavos] = React.useState<number>(0);
    const [displayValue, setDisplayValue] = React.useState<string>('0,00');
    const [isFocused, setIsFocused] = React.useState(false);

    // Converte string formatada para centavos
    const parseToCentavos = (str: string | undefined): number => {
      if (!str) return 0;

      // Remove tudo exceto dígitos
      const digitsOnly = str.replace(/\D/g, '');
      if (!digitsOnly) return 0;

      const num = parseInt(digitsOnly, 10);
      return isNaN(num) ? 0 : num;
    };

    // Formata centavos para exibição (1000 = "10,00", 123456 = "1.234,56")
    const formatFromCentavos = (cents: number): string => {
      const reais = Math.floor(cents / 100);
      const centavosResto = cents % 100;

      // Formata os reais com separador de milhares
      const reaisFormatted = reais.toLocaleString('pt-BR');

      // Garante 2 dígitos nos centavos
      const centavosFormatted = centavosResto.toString().padStart(2, '0');

      return `${reaisFormatted},${centavosFormatted}`;
    };

    // Converte centavos para string decimal no formato BR (1000 = "10,00" para API)
    const centavosToDecimalString = (cents: number): string => {
      const decimal = cents / 100;
      // Retorna no formato BR com vírgula (não ponto)
      return decimal.toFixed(2).replace('.', ',');
    };

    // Sincroniza com prop value externa
    React.useEffect(() => {
      if (value === undefined || value === null || value === '') {
        setCentavos(0);
        setDisplayValue('0,00');
        return;
      }

      // Se já está em formato de centavos brutos (apenas dígitos)
      if (/^\d+$/.test(value)) {
        const cents = parseInt(value, 10);
        setCentavos(cents);
        setDisplayValue(formatFromCentavos(cents));
        return;
      }

      // Parse de formato monetário (pode ter vírgula, ponto, R$, etc)
      const cleanValue = value.toString().replace(/[^\d,.-]/g, '');

      // Converte para número decimal
      let decimalValue: number;
      if (cleanValue.includes(',')) {
        // Formato BR: 1.234,56
        const normalized = cleanValue.replace(/\./g, '').replace(',', '.');
        decimalValue = parseFloat(normalized);
      } else if (cleanValue.includes('.')) {
        // Formato US ou decimal: 1234.56
        decimalValue = parseFloat(cleanValue);
      } else {
        // Apenas dígitos
        decimalValue = parseFloat(cleanValue);
      }

      if (!isNaN(decimalValue)) {
        const cents = Math.round(decimalValue * 100);
        setCentavos(cents);
        setDisplayValue(formatFromCentavos(cents));
      } else {
        setCentavos(0);
        setDisplayValue('0,00');
      }
    }, [value]);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      // Permite: backspace, delete, tab, escape, enter
      if ([8, 9, 27, 13, 46].includes(e.keyCode)) {
        if (e.keyCode === 8 || e.keyCode === 46) { // Backspace ou Delete
          e.preventDefault();
          // Remove o último dígito (divide por 10)
          const newCentavos = Math.floor(centavos / 10);
          setCentavos(newCentavos);
          setDisplayValue(formatFromCentavos(newCentavos));

          const decimalString = centavosToDecimalString(newCentavos);
          onValueChange?.(decimalString, name);
        }
        return;
      }

      // Permite apenas números
      if (e.key >= '0' && e.key <= '9') {
        e.preventDefault();
        // Adiciona o dígito à direita
        const newCentavos = centavos * 10 + parseInt(e.key, 10);

        // Limita a 9 dígitos (99.999.999,99 = 9.999.999.999 centavos)
        if (newCentavos <= 9999999999) {
          setCentavos(newCentavos);
          setDisplayValue(formatFromCentavos(newCentavos));

          const decimalString = centavosToDecimalString(newCentavos);
          onValueChange?.(decimalString, name);
        }
      } else {
        // Bloqueia qualquer outra tecla
        e.preventDefault();
      }
    };

    const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(true);
      // Seleciona todo o texto ao focar
      e.target.select();
    };

    const handleBlur = () => {
      setIsFocused(false);
      // Ao perder o foco, garante que o valor seja atualizado
      const decimalString = centavosToDecimalString(centavos);
      onValueChange?.(decimalString, name);
    };

    return (
      <input
        {...props}
        ref={ref}
        type="text"
        name={name}
        value={displayValue}
        onKeyDown={handleKeyDown}
        onFocus={handleFocus}
        onBlur={handleBlur}
        disabled={disabled}
        placeholder={placeholder}
        inputMode="numeric"
        autoComplete="off"
        className={cn(
          'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          isFocused && 'ring-2 ring-ring ring-offset-2',
          className
        )}
      />
    );
  }
);

CurrencyInput.displayName = 'CurrencyInput';

export default CurrencyInput;
