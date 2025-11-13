import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { categoriesAPI } from '../../utils/api';
import CategoryForm from './CategoryForm';

const Categories = () => {
  const { t } = useTranslation();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await categoriesAPI.getAll();
      setCategories(response.data);
    } catch (err) {
      setError('Erro ao carregar categorias');
      console.error('Load categories error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddCategory = () => {
    setEditingCategory(null);
    setShowForm(true);
  };

  const handleEditCategory = (category) => {
    setEditingCategory(category);
    setShowForm(true);
  };

  const handleDeleteCategory = async (categoryId) => {
    if (!window.confirm(t('categories.confirmDelete'))) return;

    try {
      await categoriesAPI.delete(categoryId);
      await loadCategories(); // Recarrega lista
    } catch (err) {
      setError(err.response?.data?.error || 'Erro ao deletar categoria');
      console.error('Delete category error:', err);
    }
  };

  const handleFormSubmit = async (formData) => {
    try {
      if (editingCategory) {
        await categoriesAPI.update(editingCategory.id, formData);
      } else {
        await categoriesAPI.create(formData);
      }
      
      setShowForm(false);
      setEditingCategory(null);
      await loadCategories(); // Recarrega lista
    } catch (err) {
      throw err; // Deixa o formulário lidar com o erro
    }
  };

  const expenseCategories = categories.filter(cat => cat.type === 'expense');
  const incomeCategories = categories.filter(cat => cat.type === 'income');

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
    <div className="categories">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="h3 mb-0">{t('categories.title')}</h2>
        
        <button
          onClick={handleAddCategory}
          className="btn btn-primary d-flex align-items-center"
        >
          <i className="bi bi-plus-circle me-2"></i>
          {t('categories.add')}
        </button>
      </div>

      {error && (
        <div className="alert alert-danger" role="alert">
          <i className="bi bi-exclamation-triangle-fill me-2"></i>
          {error}
        </div>
      )}

      <div className="row">
        {/* Categorias de Despesas */}
        <div className="col-lg-6 mb-4">
          <div className="card h-100">
            <div className="card-header">
              <h5 className="card-title mb-0 d-flex align-items-center">
                <i className="bi bi-arrow-down-circle text-danger me-2"></i>
                {t('categories.expense')} ({expenseCategories.length})
              </h5>
            </div>
            <div className="card-body">
              {expenseCategories.length === 0 ? (
                <div className="text-center text-muted py-4">
                  <i className="bi bi-tags display-6 mb-3"></i>
                  <p>Nenhuma categoria de despesa</p>
                </div>
              ) : (
                <div className="list-group list-group-flush">
                  {expenseCategories.map((category) => (
                    <div key={category.id} className="list-group-item d-flex align-items-center justify-content-between px-0">
                      <div className="d-flex align-items-center">
                        <div 
                          className="rounded-circle d-flex align-items-center justify-content-center me-3"
                          style={{
                            width: '40px',
                            height: '40px',
                            backgroundColor: category.color
                          }}
                        >
                          <i className={`bi bi-${category.icon} text-white`}></i>
                        </div>
                        <div>
                          <h6 className="mb-0">{category.name}</h6>
                          <small className="text-muted">{category.color}</small>
                        </div>
                      </div>
                      
                      <div className="btn-group" role="group">
                        <button
                          onClick={() => handleEditCategory(category)}
                          className="btn btn-outline-primary btn-sm"
                          title={t('common.edit')}
                        >
                          <i className="bi bi-pencil"></i>
                        </button>
                        <button
                          onClick={() => handleDeleteCategory(category.id)}
                          className="btn btn-outline-danger btn-sm"
                          title={t('common.delete')}
                        >
                          <i className="bi bi-trash"></i>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Categorias de Receitas */}
        <div className="col-lg-6 mb-4">
          <div className="card h-100">
            <div className="card-header">
              <h5 className="card-title mb-0 d-flex align-items-center">
                <i className="bi bi-arrow-up-circle text-success me-2"></i>
                {t('categories.income')} ({incomeCategories.length})
              </h5>
            </div>
            <div className="card-body">
              {incomeCategories.length === 0 ? (
                <div className="text-center text-muted py-4">
                  <i className="bi bi-tags display-6 mb-3"></i>
                  <p>Nenhuma categoria de receita</p>
                </div>
              ) : (
                <div className="list-group list-group-flush">
                  {incomeCategories.map((category) => (
                    <div key={category.id} className="list-group-item d-flex align-items-center justify-content-between px-0">
                      <div className="d-flex align-items-center">
                        <div 
                          className="rounded-circle d-flex align-items-center justify-content-center me-3"
                          style={{
                            width: '40px',
                            height: '40px',
                            backgroundColor: category.color
                          }}
                        >
                          <i className={`bi bi-${category.icon} text-white`}></i>
                        </div>
                        <div>
                          <h6 className="mb-0">{category.name}</h6>
                          <small className="text-muted">{category.color}</small>
                        </div>
                      </div>
                      
                      <div className="btn-group" role="group">
                        <button
                          onClick={() => handleEditCategory(category)}
                          className="btn btn-outline-primary btn-sm"
                          title={t('common.edit')}
                        >
                          <i className="bi bi-pencil"></i>
                        </button>
                        <button
                          onClick={() => handleDeleteCategory(category.id)}
                          className="btn btn-outline-danger btn-sm"
                          title={t('common.delete')}
                        >
                          <i className="bi bi-trash"></i>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Modal do Formulário */}
      {showForm && (
        <CategoryForm
          show={showForm}
          onHide={() => {
            setShowForm(false);
            setEditingCategory(null);
          }}
          onSubmit={handleFormSubmit}
          category={editingCategory}
        />
      )}
    </div>
  );
};

export default Categories;