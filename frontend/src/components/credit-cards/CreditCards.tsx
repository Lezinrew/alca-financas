import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { formatCurrency, accountsAPI } from '../../utils/api';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';
import CreditCardForm from './CreditCardForm';
import { CreditCard, CreditCardPayload } from '../../types/credit-card';
import { AccountRecord, accountToCreditCard, getDaysUntilClosing } from './creditCardUtils';
import './credit-cards.css';

const CreditCards: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [revision, setRevision] = useState(0);
  const [showCardForm, setShowCardForm] = useState(false);
  const [editingCard, setEditingCard] = useState<CreditCard | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const cardsRequest = useCallback(async (signal: AbortSignal) => {
    const response = await accountsAPI.getAll({ signal, skipCache: true });
    const accounts: AccountRecord[] = Array.isArray(response.data) ? response.data : [];
    return { data: accounts.filter(acc => acc.type === 'credit_card' && acc.is_active).map(accountToCreditCard) };
  }, []);
  const cards = useKeyedRequest<CreditCard[]>(`cards:${revision}`, isAuthenticated && !authLoading, cardsRequest);
  const reload = () => setRevision(value => value + 1);

  // Fecha menu ao clicar fora
  useEffect(() => {
    if (!openMenuId) return;
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('.card-menu')) setOpenMenuId(null);
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [openMenuId]);

  const handleCardClick = (card: CreditCard) => navigate(`/credit-cards/${card.id}`);

  const handleCardFormSubmit = async (cardData: CreditCardPayload) => {
    const accountData: Record<string, unknown> = {
      name: cardData.name,
      type: 'credit_card',
      initial_balance: cardData.limit, // Limite total do cartão
      color: cardData.color,
      icon: cardData.icon,
      is_active: cardData.is_active,
      closing_day: cardData.closingDay,
      due_day: cardData.dueDay,
      card_type: cardData.card_type,
      account_id: cardData.account_id,
    };
    if (editingCard) {
      // Nunca reenvia current_balance na edição: zeraria o valor já usado do cartão.
      await accountsAPI.update(editingCard.id, accountData);
    } else {
      await accountsAPI.create({ ...accountData, current_balance: 0 });
    }
    reload();
  };

  const handleAddCard = () => {
    setEditingCard(null);
    setShowCardForm(true);
  };

  const calculateUsedPercentage = (card: CreditCard) => {
    const used = card.used ?? 0;
    if (!card.limit) return 0;
    return Math.min(100, Math.max(0, (used / card.limit) * 100));
  };

  if (authLoading || cards.loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]" role="status" aria-busy="true">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-slate-600 dark:text-slate-400">Carregando cartões...</p>
        </div>
      </div>
    );
  }

  const list = cards.data ?? [];

  return (
    <div className="cc space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Cartões de crédito</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Gerencie seus cartões e faturas</p>
        </div>
        <button
          type="button"
          onClick={handleAddCard}
          className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          <i className="bi bi-plus-circle" aria-hidden="true"></i>
          Novo cartão de crédito
        </button>
      </div>

      {cards.error ? (
        <div className="cc-error" role="alert">
          <span>Cartões indisponíveis. {cards.error}</span>
          <button type="button" className="cc-retry" onClick={reload}>Tentar novamente</button>
        </div>
      ) : list.length === 0 ? (
        <div className="card-base p-12 text-center">
          <div className="max-w-md mx-auto">
            <div className="mb-6">
              <div className="w-48 h-48 mx-auto bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-900/30 dark:to-purple-900/30 rounded-full flex items-center justify-center">
                <i className="bi bi-credit-card text-6xl text-blue-600 dark:text-blue-400" aria-hidden="true"></i>
              </div>
            </div>
            <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">Nenhum cartão de crédito cadastrado</h3>
            <p className="text-slate-600 dark:text-slate-300 mb-6">Adicione um cartão de crédito para começar a controlar suas despesas.</p>
            <button
              type="button"
              onClick={handleAddCard}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors inline-flex items-center gap-2"
            >
              <i className="bi bi-plus-circle" aria-hidden="true"></i>
              Adicionar Cartão
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {list.map((card) => {
            const available = card.available ?? (card.limit ?? 0) - (card.used ?? 0);
            const usedPercentage = calculateUsedPercentage(card);
            const daysUntilClosing = getDaysUntilClosing(card.closingDay);

            return (
              <div key={card.id} className="card-base p-6 hover:shadow-lg transition-shadow">
                {/* Card Header */}
                <div className="flex items-start justify-between mb-4">
                  <button
                    type="button"
                    className="flex items-center gap-3 flex-1 text-left"
                    onClick={() => handleCardClick(card)}
                  >
                    <div
                      className="w-12 h-12 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: card.color }}
                    >
                      <i className="bi bi-credit-card-fill text-white text-xl" aria-hidden="true"></i>
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-900 dark:text-white">{card.name}</h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Fecha dia {card.closingDay}</p>
                    </div>
                  </button>
                  <div className="relative card-menu">
                    <button
                      type="button"
                      className="cc-icon-button"
                      aria-label={`Mais ações para ${card.name}`}
                      aria-haspopup="menu"
                      aria-expanded={openMenuId === card.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenMenuId(openMenuId === card.id ? null : card.id);
                      }}
                    >
                      <i className="bi bi-three-dots-vertical" aria-hidden="true"></i>
                    </button>
                    {openMenuId === card.id && (
                      <div role="menu" className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 z-50">
                        <button
                          type="button"
                          role="menuitem"
                          className="w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenMenuId(null);
                            setEditingCard(card);
                            setShowCardForm(true);
                          }}
                        >
                          <i className="bi bi-pencil text-blue-600 dark:text-blue-400" aria-hidden="true"></i>
                          <span>Editar</span>
                        </button>
                        <button
                          type="button"
                          role="menuitem"
                          className="w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenMenuId(null);
                            handleCardClick(card);
                          }}
                        >
                          <i className="bi bi-list-ul text-blue-600 dark:text-blue-400" aria-hidden="true"></i>
                          <span>Ver despesas</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Days Until Closing */}
                <div className="mb-4">
                  <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 rounded-full text-xs font-medium">
                    <i className="bi bi-calendar-check" aria-hidden="true"></i>
                    {daysUntilClosing === 0
                      ? 'Sua próxima fatura fecha hoje'
                      : `Sua próxima fatura fecha em ${daysUntilClosing} ${daysUntilClosing === 1 ? 'dia' : 'dias'}`}
                  </div>
                </div>

                {/* Limit Info */}
                <button type="button" className="w-full space-y-4 text-left" onClick={() => handleCardClick(card)}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 dark:text-slate-400">Limite Disponível</span>
                    <span className={`text-lg font-bold ${available >= 0
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : 'text-red-600 dark:text-red-400'
                      }`}>
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

                  <div className="pt-4 border-t border-slate-200 dark:border-slate-700/50">
                    <div className="flex items-center justify-between text-sm">
                      <div>
                        <span className="text-slate-500 dark:text-slate-400">Usado: </span>
                        <span className="font-semibold text-slate-900 dark:text-white">{formatCurrency(card.used ?? 0)}</span>
                      </div>
                      <span className="text-blue-600 dark:text-blue-400 font-medium">Ver detalhes →</span>
                    </div>
                  </div>
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal de Criar/Editar Cartão */}
      {showCardForm && (
        <CreditCardForm
          onHide={() => {
            setShowCardForm(false);
            setEditingCard(null);
          }}
          onSubmit={handleCardFormSubmit}
          card={editingCard}
        />
      )}
    </div>
  );
};

export default CreditCards;
