-- Migração: Adicionar tabela de conversas do chatbot
-- Data: 2026-03-05
-- Descrição: Armazena metadados das conversas para validação de ownership

-- Criar tabela de conversas do chatbot
CREATE TABLE IF NOT EXISTS chatbot_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    UNIQUE(user_id, conversation_id)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_chatbot_conversations_user_id
    ON chatbot_conversations(user_id);

CREATE INDEX IF NOT EXISTS idx_chatbot_conversations_conversation_id
    ON chatbot_conversations(conversation_id);

CREATE INDEX IF NOT EXISTS idx_chatbot_conversations_active
    ON chatbot_conversations(user_id, is_active)
    WHERE is_active = true;

-- Trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_chatbot_conversations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_chatbot_conversations_updated_at
    BEFORE UPDATE ON chatbot_conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_chatbot_conversations_updated_at();

-- Comentários para documentação
COMMENT ON TABLE chatbot_conversations IS 'Armazena metadados das conversas do chatbot para controle de segurança e ownership';
COMMENT ON COLUMN chatbot_conversations.user_id IS 'ID do usuário dono da conversa';
COMMENT ON COLUMN chatbot_conversations.conversation_id IS 'ID da conversa retornado pelo OpenClaw';
COMMENT ON COLUMN chatbot_conversations.metadata IS 'Metadados adicionais da conversa (título, tags, etc)';
COMMENT ON COLUMN chatbot_conversations.is_active IS 'Indica se a conversa está ativa ou foi arquivada';
