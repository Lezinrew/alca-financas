import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { transactionsAPI, categoriesAPI, formatCurrency, formatDate } from '../../utils/api';
import TransactionForm from './TransactionForm';
import TransactionList from './TransactionList';

const Transactions = () => {
  const { t } = useTranslation();
  const [transactions, setTransactions] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState(null);
  
  // Filtros
  const [filters, setFilters] = useState({
    month: new Date().getMonth() + 1,
    year: new Date().getFullYear(),
    category_id: '',
    type: ''
  });

  useEffect(() => {
    loadData();
  }, [filters]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');
      
      const [transactionsRes, categoriesRes] = await Promise.all([
        transactionsAPI.getAll(filters),
        categoriesAPI.getAll()
      ]);
      
      setTransactions(transactionsRes.data);
      // Backend devolve categorias com 'id' string; garantir string
      setCategories(categoriesRes.data.map((c: any) => ({ ...c, id: String(c.id) })));
    } catch (err) {
      setError('Erro ao carregar transações');
      console.error('Load transactions error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddTransaction = () => {
    setEditingTransaction(null);
    setShowForm(true);
  };

  const handleEditTransaction = (transaction) => {
    setEditingTransaction(transaction);
    setShowForm(true);
  };

  const handleDeleteTransaction = async (transactionId) => {
    if (!window.confirm(t('transactions.confirmDelete'))) return;

    try {
      await transactionsAPI.delete(transactionId);
      await loadData(); // Recarrega lista
    } catch (err) {
      setError('Erro ao deletar transação');
      console.error('Delete transaction error:', err);
    }
  };

  const handleFormSubmit = async (formData) => {
    try {
      if (editingTransaction) {
        await transactionsAPI.update(editingTransaction.id, formData);
      } else {
        await transactionsAPI.create(formData);
      }
      
      setShowForm(false);
      setEditingTransaction(null);
      await loadData(); // Recarrega lista
    } catch (err) {
      throw err; // Deixa o formulário lidar com o erro
    }
  };

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const months = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ];

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 5 }, (_, i) => currentYear - 2 + i);

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
        <div className="text-center">
          <div className="loading-spinner mb-3"></div>
          <p className="text-muted">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="transactions">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="h3 mb-0">{t('transactions.title')}</h2>
        
        <button
          onClick={handleAddTransaction}
          className="btn btn-primary d-flex align-items-center"
        >
          <i className="bi bi-plus-circle me-2"></i>
          {t('transactions.add')}
        </button>
      </div>

      {error && (
        <div className="alert alert-danger" role="alert">
          <i className="bi bi-exclamation-triangle-fill me-2"></i>
          {error}
        </div>
      )}

      {/* Filtros */}
      <div className="card mb-4">
        <div className="card-body">
          <div className="row g-3">
            <div className="col-md-3">
              <label className="form-label">{t('common.filter')} por Mês</label>
              <select
                className="form-select"
                value={filters.month}
                onChange={(e) => handleFilterChange('month', e.target.value)}
              >
                {months.map((month, index) => (
                  <option key={index} value={index + 1}>
                    {month}
                  </option>
                ))}
              </select>
            </div>
            
            <div className="col-md-3">
              <label className="form-label">Ano</label>
              <select
                className="form-select"
                value={filters.year}
                onChange={(e) => handleFilterChange('year', e.target.value)}
              >
                {years.map(year => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
            
            <div className="col-md-3">
              <label className="form-label">{t('transactions.category')}</label>
              <select
                className="form-select"
                value={filters.category_id}
                onChange={(e) => handleFilterChange('category_id', e.target.value)}
              >
                <option value="">Todas as categorias</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </div>
            
            <div className="col-md-3">
              <label className="form-label">{t('transactions.type')}</label>
              <select
                className="form-select"
                value={filters.type}
                onChange={(e) => handleFilterChange('type', e.target.value)}
              >
                <option value="">Todos os tipos</option>
                <option value="income">{t('transactions.income')}</option>
                <option value="expense">{t('transactions.expense')}</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Lista de Transações */}
      <TransactionList
        transactions={transactions}
        onEdit={handleEditTransaction}
        onDelete={handleDeleteTransaction}
      />

      {/* Modal do Formulário */}
      {showForm && (
        <TransactionForm
          show={showForm}
          onHide={() => {
            setShowForm(false);
            setEditingTransaction(null);
          }}
          onSubmit={handleFormSubmit}
          categories={categories}
          transaction={editingTransaction}
        />
      )}
    </div>
  );
};

export default Transactions;