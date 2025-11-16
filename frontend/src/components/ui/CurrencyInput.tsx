import React, { useState, useEffect } from 'react';

interface CurrencyInputProps {
  id?: string;
  name: string;
  value: number | string;
  onChange: (e: { target: { name: string; value: string } }) => void;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  className?: string;
  autoComplete?: string;
}

const CurrencyInput: React.FC<CurrencyInputProps> = ({
  id,
  name,
  value,
  onChange,
  placeholder = '0,00',
  disabled = false,
  required = false,
  className = '',
  autoComplete = 'transaction-amount'
}) => {
  const [displayValue, setDisplayValue] = useState<string>('');

  // Formata número para moeda brasileira (1234.56 -> "1.234,56")
  const formatCurrency = (num: number | string): string => {
    if (num === '' || num === null || num === undefined) return '';

    const numValue = typeof num === 'string' ? parseFloat(num) : num;
    if (isNaN(numValue)) return '';

    return numValue.toLocaleString('pt-BR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  };

  // Remove formatação e retorna apenas números (1.234,56 -> 1234.56)
  const unformatCurrency = (formatted: string): string => {
    if (!formatted) return '';

    // Remove pontos de milhares e troca vírgula por ponto
    const cleaned = formatted.replace(/\./g, '').replace(',', '.');
    const num = parseFloat(cleaned);

    return isNaN(num) ? '' : num.toString();
  };

  // Atualiza display quando value prop muda
  useEffect(() => {
    if (value !== undefined && value !== null) {
      setDisplayValue(formatCurrency(value));
    }
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const input = e.target.value;

    // Permite apenas números, vírgula e ponto
    const cleaned = input.replace(/[^\d,]/g, '');

    // Limita a uma vírgula
    const parts = cleaned.split(',');
    let formatted = parts[0];
    if (parts.length > 1) {
      // Limita a 2 casas decimais
      formatted = parts[0] + ',' + parts[1].substring(0, 2);
    }

    setDisplayValue(formatted);

    // Envia valor não formatado para o parent
    const unformatted = unformatCurrency(formatted);
    onChange({
      target: {
        name,
        value: unformatted
      }
    });
  };

  const handleBlur = () => {
    // Formata completamente ao sair do campo
    const unformatted = unformatCurrency(displayValue);
    if (unformatted) {
      const formatted = formatCurrency(parseFloat(unformatted));
      setDisplayValue(formatted);
    }
  };

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    // Seleciona todo o texto ao focar
    e.target.select();
  };

  return (
    <input
      type="text"
      id={id}
      name={name}
      className={className}
      value={displayValue}
      onChange={handleChange}
      onBlur={handleBlur}
      onFocus={handleFocus}
      placeholder={placeholder}
      disabled={disabled}
      required={required}
      autoComplete={autoComplete}
      aria-invalid="false"
      inputMode="decimal"
    />
  );
};

export default CurrencyInput;
