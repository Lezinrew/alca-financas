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