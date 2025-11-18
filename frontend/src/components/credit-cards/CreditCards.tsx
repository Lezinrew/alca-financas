import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { formatCurrency, categoriesAPI } from '../../utils/api';
import CreditCardExpenseForm from './CreditCardExpenseForm';
import CreditCardForm from './CreditCardForm';
import { CreditCard, CreditCardPayload } from '../../types/credit-card';

interface Category {
  id: string;
  name: string;
  type: 'income' | 'expense';
  color: string;
  icon: string;
}

const CreditCards: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [cards, setCards] = useState<CreditCard[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [showCardForm, setShowCardForm] = useState(false);
  const [selectedCard, setSelectedCard] = useState<CreditCard | null>(null);
  const [editingCard, setEditingCard] = useState<CreditCard | null>(null);
  const [activeTab, setActiveTab] = useState<'open' | 'closed'>('open');

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      loadCards();
    }
  }, [isAuthenticated, authLoading]);

  const loadCards = async () => {
    try {
      setLoading(true);
      setError('');

      // Carrega categorias
      const categoriesRes = await categoriesAPI.getAll();
      setCategories(categoriesRes.data);

      // Carrega contas do tipo credit_card
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const response = await fetch(`${API_URL}/api/accounts`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        const accounts = await response.json();
        // Filtra apenas contas do tipo credit_card e converte para o formato de CreditCard
        const creditCards = accounts
          .filter((acc: any) => acc.type === 'credit_card' && acc.is_active)
          .map((acc: any) => ({
            id: acc.id,
            name: acc.name,
            limit: acc.initial_balance || 0, // Usa initial_balance como limite
            used: (acc.initial_balance || 0) - (acc.current_balance || 0), // Calcula usado
            closingDay: acc.closing_day || 10, // TODO: Adicionar campo no backend
            dueDay: acc.due_day || 15, // TODO: Adicionar campo no backend
            color: acc.color || '#6366f1',
            icon: acc.icon || 'credit-card',
            is_active: acc.is_active,
            account_id: acc.account_id,
            card_type: acc.card_type
          }));
        setCards(creditCards);
      }
    } catch (err) {
      setError('Erro ao carregar cartões');
      console.error('Load cards error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCardClick = (card: CreditCard) => {
    // Navega para a página de detalhes do cartão
    navigate(`/credit-cards/${card.id}`);
  };

  const handleExpenseSubmit = async (expenseData: any) => {
    try {
      // TODO: Salvar no backend quando a API estiver pronta
      console.log('Despesa salva:', expenseData);

      setShowExpenseForm(false);
      setSelectedCard(null);

      // Recarrega os cartões para atualizar os valores
      await loadCards();
    } catch (err: any) {
      throw err;
    }
  };

  const handleCardFormSubmit = async (cardData: CreditCardPayload) => {
    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const url = editingCard
        ? `${API_URL}/api/accounts/${editingCard.id}`
        : `${API_URL}/api/accounts`;

      const accountData = {
        name: cardData.name,
        type: 'credit_card',
        initial_balance: cardData.limit,
        current_balance: cardData.limit, // Inicia com o limite disponível
        color: cardData.color,
        icon: cardData.icon,
        is_active: cardData.is_active,
        closing_day: cardData.closingDay, // TODO: Backend precisa suportar
        due_day: cardData.dueDay // TODO: Backend precisa suportar
      };

      const response = await fetch(url, {
        method: editingCard ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(accountData)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Erro ao salvar cartão');
      }

      setShowCardForm(false);
      setEditingCard(null);
      await loadCards();
    } catch (err: any) {
      throw err;
    }
  };

  const handleAddCard = () => {
    setEditingCard(null);
    setShowCardForm(true);
  };

  const calculateAvailable = (card: CreditCard) => {
    const used = card.used ?? 0;
    return card.limit - used;
  };

  const calculateUsedPercentage = (card: CreditCard) => {
    const used = card.used ?? 0;
    if (card.limit === 0) return 0;
    return (used / card.limit) * 100;
  };

  const getNextClosingDate = (closingDay: number) => {
    const today = new Date();
    const currentMonth = today.getMonth();
    const currentYear = today.getFullYear();
    const closingDate = new Date(currentYear, currentMonth, closingDay);

    if (today > closingDate) {
      closingDate.setMonth(currentMonth + 1);
    }

    return closingDate;
  };

  const getDaysUntilClosing = (closingDay: number) => {
    const today = new Date();
    const closingDate = getNextClosingDate(closingDay);
    const diffTime = closingDate.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-slate-600 dark:text-slate-400">Carregando cartões...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Cartões de crédito</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Gerencie seus cartões e faturas</p>
        </div>
        <button
          onClick={handleAddCard}
          className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          <i className="bi bi-plus-circle"></i>
          Novo cartão de crédito
        </button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400"></i>
          <span className="text-red-800 dark:text-red-200">{error}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="card-base">
        <div className="flex border-b border-slate-200 dark:border-slate-700/50">
          <button
            onClick={() => setActiveTab('open')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'open'
                ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            Faturas abertas
          </button>
          <button
            onClick={() => setActiveTab('closed')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'closed'
                ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            Faturas fechadas
          </button>
        </div>
      </div>

      {/* Cards Grid */}
      {cards.length === 0 ? (
        <div className="card-base p-12 text-center">
          <div className="max-w-md mx-auto">
            <div className="mb-6">
              <div className="w-48 h-48 mx-auto bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-900/30 dark:to-purple-900/30 rounded-full flex items-center justify-center">
                <i className="bi bi-credit-card text-6xl text-blue-600 dark:text-blue-400"></i>
              </div>
            </div>

            <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
              {activeTab === 'open'
                ? 'Nenhum cartão de crédito cadastrado'
                : 'Você não possui faturas fechadas no momento'}
            </h3>
            <p className="text-slate-600 dark:text-slate-300 mb-6">
              {activeTab === 'open'
                ? 'Adicione um cartão de crédito para começar a controlar suas despesas.'
                : 'Confira seus cartões para saber mais.'}
            </p>

            {activeTab === 'open' && (
              <button
                onClick={handleAddCard}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors inline-flex items-center gap-2"
              >
                <i className="bi bi-plus-circle"></i>
                Adicionar Cartão
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {cards.map((card) => {
            const available = calculateAvailable(card);
            const usedPercentage = calculateUsedPercentage(card);
            const daysUntilClosing = getDaysUntilClosing(card.closingDay);

            return (
              <div
                key={card.id}
                className="card-base p-6 hover:shadow-lg transition-shadow cursor-pointer"
                onClick={() => handleCardClick(card)}
              >
                {/* Card Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-12 h-12 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: card.color }}
                    >
                      <i className="bi bi-credit-card-fill text-white text-xl"></i>
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-900 dark:text-white">{card.name}</h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Fecha dia {card.closingDay}
                      </p>
                    </div>
                  </div>
                  <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors">
                    <i className="bi bi-three-dots-vertical text-slate-600 dark:text-slate-400"></i>
                  </button>
                </div>

                {/* Days Until Closing */}
                <div className="mb-4">
                  <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 rounded-full text-xs font-medium">
                    <i className="bi bi-calendar-check"></i>
                    Sua próxima fatura vence em {daysUntilClosing} {daysUntilClosing === 1 ? 'dia' : 'dias'}
                  </div>
                </div>

                {/* Limit Info */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 dark:text-slate-400">Limite Disponível</span>
                    <span className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                      {formatCurrency(available)}
                    </span>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-slate-500 dark:text-slate-400">Valor total</span>
                      <span className="text-xs text-slate-500 dark:text-slate-400">{formatCurrency(card.limit)}</span>
                    </div>
                    <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-emerald-500 to-blue-500 rounded-full transition-all duration-300"
                        style={{ width: `${usedPercentage}%` }}
                      ></div>
                    </div>
                  </div>
                </div>

                {/* Footer */}
                <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700/50">
                  <div className="flex items-center justify-between text-sm">
                    <div>
                      <span className="text-slate-500 dark:text-slate-400">Usado: </span>
                      <span className="font-semibold text-slate-900 dark:text-white">{formatCurrency(card.used ?? 0)}</span>
                    </div>
                    <button className="text-blue-600 dark:text-blue-400 hover:underline font-medium">
                      Ver detalhes
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal de Despesa do Cartão */}
      {showExpenseForm && selectedCard && (
        <CreditCardExpenseForm
          show={showExpenseForm}
          onHide={() => {
            setShowExpenseForm(false);
            setSelectedCard(null);
          }}
          onSubmit={handleExpenseSubmit}
          card={selectedCard}
          categories={categories}
        />
      )}

      {/* Modal de Criar/Editar Cartão */}
      <CreditCardForm
        show={showCardForm}
        onHide={() => {
          setShowCardForm(false);
          setEditingCard(null);
        }}
        onSubmit={handleCardFormSubmit}
        card={editingCard}
      />
    </div>
  );
};

export default CreditCards;
