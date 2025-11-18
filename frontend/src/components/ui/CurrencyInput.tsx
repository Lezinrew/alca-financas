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
      placeholder = 'R$ 0,00',
      prefix = 'R$ ',
      decimalSeparator = ',',
      groupSeparator = '.',
      ...props
    },
    ref
  ) => {
    return (
      <CurrencyInputField
        {...props}
        ref={ref}
        decimalsLimit={2}
        value={value}
        defaultValue={defaultValue}
        prefix={prefix}
        decimalSeparator={decimalSeparator}
        groupSeparator={groupSeparator}
        intlConfig={{ locale: 'pt-BR', currency: 'BRL' }}
        disableGroupSeparators={false}
        className={cn(
          'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        onValueChange={(val, name) => onValueChange?.(val, name)}
        disabled={disabled}
        placeholder={placeholder}
        inputMode="decimal"
      />
    );
  }
);

CurrencyInput.displayName = 'CurrencyInput';

export default CurrencyInput;
