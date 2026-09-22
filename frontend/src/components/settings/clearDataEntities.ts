/**
 * Fonte única das entidades removidas por "Limpar todos os dados".
 * Usada tanto na lista de aviso do diálogo quanto no resumo do resultado,
 * para que o usuário confirme exatamente o que será apagado.
 */
export interface ClearDataEntity {
  /** Rótulo em pt-BR, no plural. */
  label: string;
  /** Chaves de `deleted` na resposta de POST /auth/data/clear somadas neste item. */
  keys: string[];
  /** Observação opcional sobre escopo (ex.: só quando o workspace é individual). */
  note?: string;
}

export const CLEAR_DATA_ENTITIES: ClearDataEntity[] = [
  { label: 'transações', keys: ['transactions'] },
  { label: 'contas', keys: ['accounts'] },
  { label: 'categorias', keys: ['categories'] },
  { label: 'contas a pagar', keys: ['financial_expenses'] },
  { label: 'metas', keys: ['goals'] },
  { label: 'linhas de planejamento por categoria', keys: ['budget_plans'] },
  { label: 'meses de planejamento', keys: ['budget_monthly'], note: 'apenas se você for o único membro do workspace' },
  { label: 'aliases de comerciante', keys: ['merchant_category_aliases_user', 'merchant_category_aliases_tenant'] },
  { label: 'conversas do assistente', keys: ['chatbot_conversations'] },
  { label: 'registros de notificação admin', keys: ['admin_notification_delivery'] },
  { label: 'linhas de auditoria admin associadas', keys: ['admin_audit_logs_target', 'admin_audit_logs_actor'] },
];

/** Texto de confirmação exigido para habilitar a exclusão. */
export const CLEAR_DATA_CONFIRMATION = 'EXCLUIR';

/** Resume as contagens devolvidas pela API usando os mesmos rótulos do aviso. */
export function summarizeDeleted(deleted: Record<string, number | undefined> | undefined): string[] {
  if (!deleted) return [];
  return CLEAR_DATA_ENTITIES.flatMap(entity => {
    const total = entity.keys.reduce((sum, key) => sum + (typeof deleted[key] === 'number' ? (deleted[key] as number) : 0), 0);
    return total > 0 ? [`${total} ${entity.label}`] : [];
  });
}
