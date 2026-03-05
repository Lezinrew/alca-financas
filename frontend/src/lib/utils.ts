import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function parseCurrencyString(value?: string | null): number {
  if (!value) return 0;
  const normalized = value.replace(/\s/g, '').replace(/\./g, '').replace(',', '.').replace('R$', '');
  const parsed = Number(normalized);
  return Number.isNaN(parsed) ? 0 : parsed;
}

/**
 * Formata um número para o formato BR de moeda (sem R$)
 * Usado para popular CurrencyInput ao editar
 * @param value - Valor numérico
 * @returns String no formato BR (ex: "1234,56")
 */
export function formatNumberToBR(value?: number | null): string {
  if (value === null || value === undefined) return '';
  if (value === 0) return '0,00';
  return value.toFixed(2).replace('.', ',');
}