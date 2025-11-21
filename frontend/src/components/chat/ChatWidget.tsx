import React, { useState, useRef, useEffect } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card } from '../ui/card';
import { Send, X, Minimize2, Maximize2, Bot } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
  suggestions?: string[];
}

const CHATBOT_API_URL = 'https://chat.alcahub.com.br/api/chat';
const CHATBOT_WS_URL = 'wss://chat.alcahub.com.br/api/chat/ws';

export const ChatWidget: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: 'Olá! Sou o assistente virtual da Alça Finanças. Como posso ajudá-lo hoje?',
      isUser: false,
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [useWebSocket, setUseWebSocket] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const { isAuthenticated } = useAuth();
  
  const getToken = () => {
    return localStorage.getItem('auth_token');
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Conectar WebSocket quando o chat for aberto
  useEffect(() => {
    if (isOpen && isAuthenticated && useWebSocket) {
      connectWebSocket();
    } else if (wsRef.current) {
      disconnectWebSocket();
    }

    return () => {
      if (wsRef.current) {
        disconnectWebSocket();
      }
    };
  }, [isOpen, isAuthenticated, useWebSocket]);

  const connectWebSocket = () => {
    const token = getToken();
    if (!token) return;

    try {
      const ws = new WebSocket(`${CHATBOT_WS_URL}?token=${token}`);
      
      ws.onopen = () => {
        setIsConnected(true);
        wsRef.current = ws;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'message') {
            const botMessage: Message = {
              id: Date.now().toString(),
              text: data.reply,
              isUser: false,
              timestamp: new Date(data.timestamp || Date.now()),
              suggestions: data.suggestions,
            };
            setMessages((prev) => [...prev, botMessage]);
            if (data.conversation_id) {
              setConversationId(data.conversation_id);
            }
          } else if (data.type === 'system') {
            const systemMessage: Message = {
              id: Date.now().toString(),
              text: data.message,
              isUser: false,
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, systemMessage]);
            if (data.conversation_id) {
              setConversationId(data.conversation_id);
            }
          } else if (data.type === 'error') {
            const errorMessage: Message = {
              id: Date.now().toString(),
              text: data.message,
              isUser: false,
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
          }
        } catch (error) {
          console.error('Erro ao processar mensagem WebSocket:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('Erro WebSocket:', error);
        setIsConnected(false);
        setUseWebSocket(false); // Fallback para HTTP
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        // Tentar reconectar após 3 segundos se o chat ainda estiver aberto
        if (isOpen && isAuthenticated) {
          setTimeout(() => {
            if (isOpen && !wsRef.current) {
              connectWebSocket();
            }
          }, 3000);
        }
      };
    } catch (error) {
      console.error('Erro ao conectar WebSocket:', error);
      setUseWebSocket(false); // Fallback para HTTP
    }
  };

  const disconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  };

  const sendMessage = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: messageText,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // Usar WebSocket se disponível
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({
          message: messageText,
          conversation_id: conversationId,
        }));
        setIsLoading(false);
        return;
      } catch (error) {
        console.error('Erro ao enviar via WebSocket:', error);
        // Fallback para HTTP
      }
    }

    // Fallback para HTTP
    try {
      const token = getToken();
      if (!token) {
        throw new Error('Não autenticado');
      }
      
      const response = await axios.post(
        CHATBOT_API_URL,
        {
          message: messageText,
          conversation_id: conversationId,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.data.reply,
        isUser: false,
        timestamp: new Date(),
        suggestions: response.data.suggestions,
      };

      if (response.data.conversation_id) {
        setConversationId(response.data.conversation_id);
      }

      setMessages((prev) => [...prev, botMessage]);
    } catch (error: any) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: error.response?.data?.detail || 'Desculpe, ocorreu um erro. Tente novamente.',
        isUser: false,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    sendMessage(suggestion);
  };

  // Só mostra o widget se estiver autenticado
  if (!isAuthenticated) {
    return null;
  }

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-emerald-500 hover:bg-emerald-600 text-white rounded-full shadow-lg flex items-center justify-center z-50 transition-all"
        aria-label="Abrir chat"
      >
        <Bot className="w-6 h-6" />
      </button>
    );
  }

  return (
    <Card className="fixed bottom-6 right-6 w-96 h-[600px] flex flex-col shadow-2xl z-50 border-2">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b bg-emerald-500 text-white rounded-t-lg">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5" />
          <h3 className="font-semibold">Assistente Virtual</h3>
          {isConnected && (
            <span className="ml-2 w-2 h-2 bg-green-300 rounded-full animate-pulse" title="Conectado em tempo real"></span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsMinimized(!isMinimized)}
            className="text-white hover:bg-emerald-600 h-8 w-8 p-0"
          >
            {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsOpen(false)}
            className="text-white hover:bg-emerald-600 h-8 w-8 p-0"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50 dark:bg-slate-900">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg p-3 ${
                    message.isUser
                      ? 'bg-emerald-500 text-white'
                      : 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white border'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{message.text}</p>
                  {message.suggestions && message.suggestions.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {message.suggestions.map((suggestion, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleSuggestionClick(suggestion)}
                          className="text-xs px-2 py-1 bg-emerald-100 dark:bg-emerald-900 text-emerald-700 dark:text-emerald-300 rounded hover:bg-emerald-200 dark:hover:bg-emerald-800 transition-colors"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-white dark:bg-slate-800 rounded-lg p-3 border">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t bg-white dark:bg-slate-800">
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Digite sua mensagem..."
                disabled={isLoading}
                className="flex-1"
              />
              <Button
                onClick={() => sendMessage()}
                disabled={!input.trim() || isLoading}
                className="bg-emerald-500 hover:bg-emerald-600"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </>
      )}
    </Card>
  );
};

