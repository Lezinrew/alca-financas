/**
 * Chave de idempotência de um envio.
 *
 * Quem chama gera a chave UMA vez por intenção do titular e reutiliza em novas
 * tentativas do mesmo envio; assim uma resposta perdida na rede não cria duas
 * execuções. `crypto.randomUUID` só existe em contexto seguro (https/localhost),
 * por isso o caminho alternativo com `getRandomValues`.
 */
export const newIdempotencyKey = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
};
