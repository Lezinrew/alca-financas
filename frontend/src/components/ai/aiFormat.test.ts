import { describe, expect, it } from 'vitest';
import {
  buildStages, effectCounts, effectTotals, formatCivilDate, formatCount, formatDecimalMoney, formatFactValue, formatInstant, formatPeriod,
  formatTotalValue, LEDGER_STATES, ledgerStateInfo, totalLabel,
} from './aiFormat';
import { IMPORT_PROPOSAL, IMPORT_REVERSAL_PROPOSAL, PAYMENT_PROPOSAL, REVERSAL_PROPOSAL, makeRun } from './fixtures';

// Intl usa espaço não separável entre o símbolo e o número; os testes comparam com espaço comum.
const plain = (value: string | null) => value?.replace(/\u00a0/g, ' ') ?? null;

describe('formatDecimalMoney: string decimal sem passar por number', () => {
  it('formata valores comuns com milhar e centavos', () => {
    expect(plain(formatDecimalMoney('1250.00'))).toBe('R$ 1.250,00');
    expect(plain(formatDecimalMoney('0.10'))).toBe('R$ 0,10');
    expect(plain(formatDecimalMoney('1000000.5'))).toBe('R$ 1.000.000,50');
    expect(plain(formatDecimalMoney('7'))).toBe('R$ 7,00');
    expect(plain(formatDecimalMoney('-45.90'))).toBe('-R$ 45,90');
  });

  it('não perde centavos em valores que um number não representa', () => {
    // Number('123456789012345678.90') vira 123456789012345680: os centavos e as unidades somem.
    expect(plain(formatDecimalMoney('123456789012345678.90'))).toBe('R$ 123.456.789.012.345.678,90');
    expect(plain(formatDecimalMoney('9007199254740993.01'))).toBe('R$ 9.007.199.254.740.993,01');
  });

  it('preserva casas extras em vez de arredondar no navegador', () => {
    expect(plain(formatDecimalMoney('0.105'))).toBe('R$ 0,105');
  });

  it('zero só aparece quando o servidor mandou zero', () => {
    expect(plain(formatDecimalMoney('0.00'))).toBe('R$ 0,00');
    expect(plain(formatDecimalMoney('-0.00'))).toBe('R$ 0,00');
  });

  it('ausência ou lixo nunca viram zero: devolve null', () => {
    for (const value of [null, undefined, '', '   ', 'abc', 'NaN', '1,250.00', '12.', '.5', 1250, 0, {}, []]) {
      expect(formatDecimalMoney(value)).toBeNull();
    }
  });

  it('usa o símbolo da moeda informada e o código quando não conhece', () => {
    expect(plain(formatDecimalMoney('10.00', 'USD'))).toBe('US$ 10,00');
    expect(plain(formatDecimalMoney('10.00', 'CHF'))).toBe('CHF 10,00');
  });
});

describe('formatFactValue', () => {
  it('value null mostra travessão e o motivo informado', () => {
    const display = formatFactValue({ value: null, unit: 'money', currency: 'BRL', missing_reason: 'Sem extrato importado neste período.' });
    expect(display).toEqual({ text: '—', missing: 'Sem extrato importado neste período.' });
  });

  it('value null sem motivo ainda explica o travessão', () => {
    const display = formatFactValue({ value: null, unit: 'money', currency: 'BRL', missing_reason: null });
    expect(display.text).toBe('—');
    expect(display.missing).toMatch(/não informou o motivo/);
  });

  it('valor em formato inesperado vira travessão com motivo, não zero', () => {
    const display = formatFactValue({ value: 'mil reais', unit: 'money', currency: 'BRL', missing_reason: null });
    expect(display.text).toBe('—');
    expect(display.missing).toMatch(/formato/);
  });

  it('formata contagem, data e texto conforme a unidade', () => {
    expect(formatFactValue({ value: '12345', unit: 'count' }).text).toBe('12.345');
    expect(formatFactValue({ value: '2026-10-05', unit: 'date' }).text).toBe('05/10/2026');
    expect(formatFactValue({ value: 'Parcial', unit: 'text' }).text).toBe('Parcial');
    expect(plain(formatFactValue({ value: '1250.00', unit: 'money', currency: 'BRL' }).text)).toBe('R$ 1.250,00');
  });
});

describe('datas', () => {
  it('data civil não muda de dia por causa de fuso', () => {
    expect(formatCivilDate('2026-10-01')).toBe('01/10/2026');
    expect(formatCivilDate('2026-10-01T00:00:00Z')).toBe('01/10/2026');
    expect(formatCivilDate('01/10/2026')).toBeNull();
  });

  it('instante de auditoria é mostrado no horário de Brasília', () => {
    // 02:30 UTC ainda é o dia anterior, 23:30, em America/Sao_Paulo.
    expect(formatInstant('2026-10-02T02:30:00Z')).toBe('01/10/2026 às 23:30');
    expect(formatInstant('não é data')).toBeNull();
    expect(formatInstant(null)).toBeNull();
  });

  it('período usa o rótulo do servidor ou o intervalo de datas', () => {
    expect(formatPeriod({ label: 'outubro/2026', start: '2026-10-01', end: '2026-10-31' })).toBe('outubro/2026');
    expect(formatPeriod({ start: '2026-09-01', end: '2026-09-30' })).toBe('01/09/2026 a 30/09/2026');
    expect(formatPeriod(null)).toBeNull();
  });

  it('contagem aceita inteiro JSON e recusa o resto', () => {
    expect(formatCount(42)).toBe('42');
    expect(formatCount(1234567)).toBe('1.234.567');
    expect(formatCount('3.5')).toBeNull();
    expect(formatCount(3.5)).toBeNull();
  });
});

describe('estados do livro', () => {
  it('conferido, registrado pago e conciliado têm rótulos e explicações diferentes', () => {
    expect(LEDGER_STATES.map(state => state.label)).toEqual(['Conferido', 'Registrado pago', 'Conciliado no extrato']);
    expect(new Set(LEDGER_STATES.map(state => state.explanation)).size).toBe(3);
    expect(ledgerStateInfo('conferido')?.explanation).toMatch(/não é baixa/);
    expect(ledgerStateInfo('registrado_pago')?.explanation).toMatch(/sem vínculo com o extrato/);
    expect(ledgerStateInfo('conciliado')?.explanation).toMatch(/extrato do banco/);
    expect(ledgerStateInfo('desconhecido')).toBeNull();
  });

  it('reconhece os estados que o backend manda fora do trio: importado e revertido', () => {
    expect(ledgerStateInfo('importado')?.label).toBe('Importado');
    // `revertido` é o state_after de toda compensação (finance/proposals.py, STATE_REVERSED).
    expect(ledgerStateInfo('revertido')?.label).toBe('Desfeito');
    expect(ledgerStateInfo('revertido')?.explanation).toMatch(/histórico é preservado/);
    // Continuam fora da legenda dos três estados que não podem ser confundidos.
    expect(LEDGER_STATES.map(state => state.id)).toEqual(['conferido', 'registrado_pago', 'conciliado']);
  });
});

describe('efeito de proposta: contagens e totais', () => {
  const rows = (pairs: Array<[string, string]>) => pairs.map(([label, value]) => `${label}=${plain(value)}`);

  it('totais usam as chaves que o backend emite e nunca mostram o nome cru do campo', () => {
    expect(['income', 'expense', 'net', 'transfer_skipped'].map(totalLabel))
      .toEqual(['Entradas', 'Saídas', 'Saldo do período', 'Transferências não importadas']);
    expect(totalLabel('chave_nova')).toBe('Outro total (chave nova)');
    expect(rows(effectTotals(IMPORT_PROPOSAL.effect)))
      .toEqual(['Entradas=R$ 5.200,00', 'Saídas=R$ 4.310,75', 'Saldo do período=R$ 889,25', 'Transferências não importadas=R$ 500,00']);
    expect(effectTotals(PAYMENT_PROPOSAL.effect)).toEqual([]);
    expect(effectTotals(null)).toEqual([]);
  });

  it('total: decimal com casas é dinheiro, inteiro é contagem, o resto é travessão', () => {
    expect(plain(formatTotalValue('310.00'))).toBe('R$ 310,00');
    expect(plain(formatTotalValue('0.00'))).toBe('R$ 0,00');
    expect(formatTotalValue('3')).toBe('3');
    expect(formatTotalValue(3)).toBe('3');
    for (const value of [null, undefined, '', 'abc', 3.5, {}]) expect(formatTotalValue(value)).toBe('—');
  });

  it('importação mostra itens novos, duplicados e transferências, inclusive quando são zero', () => {
    expect(rows(effectCounts(IMPORT_PROPOSAL.effect)))
      .toEqual(['Itens novos=42', 'Duplicados (não serão importados)=3', 'Transferências (não serão importadas)=1']);
    expect(rows(effectCounts({ state_after: 'importado', before: null, after: null, items_new: 5, items_duplicate: 0 })))
      .toEqual(['Itens novos=5', 'Duplicados (não serão importados)=0']);
    expect(rows(effectCounts(IMPORT_PROPOSAL.effect, true)))
      .toEqual(['Itens importados=42', 'Duplicados (não importados)=3', 'Transferências (não importadas)=1']);
  });

  it('baixa e compensação de baixa não mostram as contagens zeradas que o backend sempre manda', () => {
    expect(effectCounts(PAYMENT_PROPOSAL.effect)).toEqual([]);
    expect(effectCounts(REVERSAL_PROPOSAL.effect)).toEqual([]);
  });

  it('compensação de importação: items_new é o que será cancelado', () => {
    expect(rows(effectCounts(IMPORT_REVERSAL_PROPOSAL.effect))).toEqual(['Lançamentos que serão cancelados=42']);
    expect(rows(effectCounts(IMPORT_REVERSAL_PROPOSAL.effect, true))).toEqual(['Lançamentos cancelados=42']);
  });

  it('contagem ausente não aparece; contagem em formato estranho vira travessão, não zero', () => {
    expect(effectCounts({ state_after: 'importado', items_new: null })).toEqual([]);
    expect(effectCounts({ state_after: 'importado', items_new: 4.5 as unknown as number })).toEqual([['Itens novos', '—']]);
  });
});

describe('buildStages: a trilha segue o que o servidor informou', () => {
  const states = (run: Parameters<typeof buildStages>[0]) => buildStages(run).map(stage => `${stage.label}:${stage.state}`);

  it('execução na fila não tem etapa em andamento', () => {
    expect(states(makeRun({ status: 'queued', progress: { stage: null, steps: [] } })))
      .toEqual(['Buscando:pending', 'Lendo:pending', 'Preparando:pending', 'Concluído:pending']);
  });

  it('marca como atual exatamente a etapa informada', () => {
    expect(states(makeRun({ status: 'running', progress: { stage: 'reading', steps: [] } })))
      .toEqual(['Buscando:done', 'Lendo:current', 'Preparando:pending', 'Concluído:pending']);
  });

  it('pergunta concluída não finge ter passado por revisão nem aplicado algo', () => {
    const labels = buildStages(makeRun({ status: 'completed', progress: { stage: 'done', steps: [] } })).map(stage => stage.label);
    expect(labels).toEqual(['Buscando', 'Lendo', 'Preparando', 'Concluído']);
  });

  it('importação aguardando revisão mostra a revisão como etapa que espera o titular', () => {
    expect(states(makeRun({ task: 'statement_import', status: 'waiting_review', progress: { stage: 'waiting_review', steps: [] }, proposal_ids: ['p'] })))
      .toEqual(['Buscando:done', 'Lendo:done', 'Preparando:done', 'Aguardando revisão:waiting', 'Aplicado:pending']);
  });

  it('aplicação em andamento aparece como "Aplicando" e só vira "Aplicado" ao concluir', () => {
    expect(states(makeRun({ task: 'apply_proposal', status: 'running', progress: { stage: 'applying', steps: [] } })))
      .toEqual(['Aguardando revisão:done', 'Aplicando:current']);
    expect(states(makeRun({ task: 'apply_proposal', status: 'completed', progress: { stage: 'done', steps: [] }, operation_ids: ['o'] })))
      .toEqual(['Aguardando revisão:done', 'Aplicado:done']);
  });

  it('revisão encerrada sem gravação não diz "Aplicado"', () => {
    const labels = buildStages(makeRun({ task: 'statement_import', status: 'completed', progress: { stage: 'done', steps: [] }, proposal_ids: ['p'] })).map(stage => stage.label);
    expect(labels[labels.length - 1]).toBe('Revisão encerrada');
  });

  it('falha e cancelamento param na etapa em que ocorreram', () => {
    expect(states(makeRun({ status: 'failed', progress: { stage: 'reading', steps: [] } })))
      .toEqual(['Buscando:done', 'Lendo:failed', 'Preparando:pending', 'Concluído:pending']);
    expect(states(makeRun({ status: 'cancelled', progress: { stage: 'preparing', steps: [] } })))
      .toEqual(['Buscando:done', 'Lendo:done', 'Preparando:cancelled', 'Concluído:pending']);
  });
});
