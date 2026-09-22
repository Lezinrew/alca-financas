import { describe, expect, it } from 'vitest';
import { parseGoalAmount } from './goalCurrency';

describe('parseGoalAmount', () => {
  it('aceita formato brasileiro com milhar e decimal', () => {
    expect(parseGoalAmount('1.500,00')).toBe(1500);
    expect(parseGoalAmount('12.345,67')).toBe(12345.67);
    expect(parseGoalAmount('R$ 1.500,50')).toBe(1500.5);
  });

  it('aceita vírgula decimal sem milhar', () => {
    expect(parseGoalAmount('1500,50')).toBe(1500.5);
    expect(parseGoalAmount('0,99')).toBe(0.99);
  });

  it('aceita ponto decimal', () => {
    expect(parseGoalAmount('1500.50')).toBe(1500.5);
    expect(parseGoalAmount('1.5')).toBe(1.5);
    expect(parseGoalAmount('1,500.25')).toBe(1500.25);
  });

  it('trata ponto único com três casas como milhar', () => {
    expect(parseGoalAmount('1.500')).toBe(1500);
    expect(parseGoalAmount('1.234.567')).toBe(1234567);
  });

  it('retorna zero para vazio ou inválido', () => {
    expect(parseGoalAmount('')).toBe(0);
    expect(parseGoalAmount('   ')).toBe(0);
    expect(parseGoalAmount('abc')).toBe(0);
    expect(parseGoalAmount(null)).toBe(0);
    expect(parseGoalAmount(undefined)).toBe(0);
    expect(parseGoalAmount('1500')).toBe(1500);
  });
});
