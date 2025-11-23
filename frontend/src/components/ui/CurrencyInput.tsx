import * as React from 'react';
import CurrencyInputField, {
  CurrencyInputProps as CurrencyInputFieldProps,
} from 'react-currency-input-field';
import { cn } from '../../lib/utils';

export interface CurrencyInputProps
  extends Omit<CurrencyInputFieldProps, 'onValueChange' | 'intlConfig'> {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string | undefined, name?: string | null) => void;
  error?: string;
}

export const CurrencyInput = React.forwardRef<HTMLInputElement, CurrencyInputProps>(
  (
    {
      className,
      value,
      defaultValue,
      onValueChange,
      disabled,
      placeholder = '0,00',
      prefix, // Se não especificado, usa '' (sem prefixo R$ no input, como Mobills)
      decimalSeparator = ',',
      groupSeparator = '.',
      ...props
    },
    ref
  ) => {
    // Força prefix vazio por padrão (como Mobills - sem R$ no input)
    const finalPrefix = prefix !== undefined ? prefix : '';
    
    // Limpa o valor para a biblioteca formatar automaticamente
    // A biblioteca react-currency-input-field formata automaticamente enquanto digita
    // Exemplo: digitar "1111" → formata para "11,11"
    // IMPORTANTE: A biblioteca espera valores numéricos limpos (sem formatação)
    const cleanValue = React.useMemo(() => {
      // Se não tem valor, retorna undefined para a biblioteca gerenciar
      if (!value && value !== '0') return undefined;
      
      if (typeof value === 'string') {
        // Remove R$, espaços e formatação existente
        let cleaned = value.replace(/R\$\s*/g, '').trim();
        if (!cleaned || cleaned === '') return undefined;
        
        // Se já está formatado (tem vírgula ou ponto), converte para número limpo
        // Remove pontos de milhares e converte vírgula para ponto
        cleaned = cleaned.replace(/\./g, '').replace(',', '.');
        const numValue = parseFloat(cleaned);
        
        // Se é um número válido, retorna como string numérica
        // A biblioteca vai formatar automaticamente
        if (!isNaN(numValue)) {
          return numValue.toString();
        }
        
        return undefined;
      }
      
      // Se é número, converte para string
      // A biblioteca vai formatar automaticamente
      if (typeof value === 'number') {
        return value.toString();
      }
      
      return value;
    }, [value]);

    return (
      <CurrencyInputField
        {...props}
        ref={ref}
        decimalsLimit={2}
        value={cleanValue}
        defaultValue={defaultValue}
        prefix={finalPrefix}
        decimalSeparator={decimalSeparator}
        groupSeparator={groupSeparator}
        disableGroupSeparators={false}
        allowDecimals={true}
        allowNegativeValue={false}
        fixedDecimalLength={2}
        className={cn(
          'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        onValueChange={(val, name, values) => {
          // A biblioteca retorna o valor formatado automaticamente
          // Com fixedDecimalLength={2} e decimalSeparator={','}, deveria formatar com vírgula
          // Mas garantimos que sempre tenha vírgula com 2 decimais
          if (val) {
            // Se já tem vírgula, passa direto (já está formatado)
            if (val.includes(',')) {
              onValueChange?.(val, name);
              return;
            }
            
            // Se não tem vírgula, formata com vírgula e 2 decimais
            const numStr = val.replace(/\./g, '');
            const numValue = parseFloat(numStr);
            
            if (!isNaN(numValue)) {
              // Formata sempre com vírgula e 2 decimais usando padrão brasileiro
              const formatted = numValue.toLocaleString('pt-BR', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              });
              // Remove R$ se existir
              const cleaned = formatted.replace(/R\$\s*/g, '').trim();
              onValueChange?.(cleaned, name);
              return;
            }
          }
          onValueChange?.(val, name);
        }}
        disabled={disabled}
        placeholder={placeholder}
        inputMode="decimal"
      />
    );
  }
);

CurrencyInput.displayName = 'CurrencyInput';

export default CurrencyInput;
