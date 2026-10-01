/**
 * Liga a tela do operador de IA no build.
 *
 * Padrão desligado: a produção não pode exibir uma função que o backend ainda
 * não ativou. Só o valor literal "true" liga; ausência, "1" ou "yes" mantêm
 * desligado, para que um engano de configuração nunca exponha a tela.
 */
export const AI_OPERATOR_ENABLED: boolean = import.meta.env.VITE_ENABLE_AI_OPERATOR === 'true';
