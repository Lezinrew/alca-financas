import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

const CategoryForm = ({ show, onHide, onSubmit, category }) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState({
    name: '',
    type: 'expense',
    color: '#6366f1',
    icon: 'circle'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Lista de ícones disponíveis
  const availableIcons = [
    'circle', 'basket', 'car-front', 'house', 'heart-pulse', 'currency-dollar',
    'briefcase', 'phone', 'wifi', 'lightning', 'fuel-pump', 'bag',
    'cart', 'cup-straw', 'trophy', 'gift', 'airplane', 'bicycle',
    'bus-front', 'train-front', 'bank', 'credit-card', 'piggy-bank',
    'cash-coin', 'graph-up-arrow', 'tools', 'hammer', 'wrench'
  ];

  // Cores predefinidas
  const availableColors = [
    '#6366f1', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
    '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6b7280',
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57',
    '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3', '#FF9F43'
  ];

  // Preenche o formulário se estiver editando
  useEffect(() => {
    if (category && show) {
      console.log('CategoryForm: Preenchendo formulário com categoria:', category);
      setFormData({
        name: category.name || '',
        type: category.type || 'expense',
        color: category.color || '#6366f1',
        icon: category.icon || 'circle'
      });
    } else if (!category && show) {
      // Reset form for new category
      console.log('CategoryForm: Resetando formulário para nova categoria');
      setFormData({
        name: '',
        type: 'expense',
        color: '#6366f1',
        icon: 'circle'
      });
    }
  }, [category, show]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Validações
      if (!formData.name.trim()) {
        throw new Error('Nome da categoria é obrigatório');
      }

      // Prepara dados para envio
      const submitData = {
        name: formData.name.trim(),
        type: formData.type,
        color: formData.color,
        icon: formData.icon
      };

      await onSubmit(submitData);
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Erro ao salvar categoria');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onHide();
    }
  };

  if (!show) return null;

  return (
    <>
      <div className="modal-backdrop fade show" style={{ position: 'fixed', zIndex: 1040 }} onClick={handleClose}></div>
      <div className="modal fade show" style={{ display: 'block', zIndex: 1050 }} tabIndex="-1" role="dialog">
        <div className="modal-dialog modal-lg" role="document" onClick={(e) => e.stopPropagation()}>
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">
                {category ? t('categories.edit') : t('categories.add')}
              </h5>
              <button
                type="button"
                className="btn-close"
                onClick={handleClose}
                disabled={loading}
              ></button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {error && (
                  <div className="alert alert-danger" role="alert">
                    <i className="bi bi-exclamation-triangle-fill me-2"></i>
                    {error}
                  </div>
                )}

              {/* Preview da Categoria */}
              <div className="text-center mb-4">
                <div 
                  className="rounded-circle d-inline-flex align-items-center justify-content-center mx-auto mb-2"
                  style={{
                    width: '80px',
                    height: '80px',
                    backgroundColor: formData.color
                  }}
                >
                  <i className={`bi bi-${formData.icon} text-white`} style={{ fontSize: '2rem' }}></i>
                </div>
                <h5 className="mb-0">{formData.name || 'Nome da Categoria'}</h5>
                <small className="text-muted">
                  {formData.type === 'income' ? t('categories.income') : t('categories.expense')}
                </small>
              </div>

              <div className="row g-3">
                  {/* Nome */}
                  <div className="col-12">
                    <label htmlFor="category-name" className="form-label">{t('categories.name')}</label>
                    <input
                      type="text"
                      id="category-name"
                      name="name"
                      className="form-control"
                      value={formData.name}
                      onChange={handleChange}
                      required
                      disabled={loading}
                      placeholder="Ex: Alimentação, Salário, etc."
                      autoComplete="category-name"
                    />
                  </div>

                  {/* Tipo */}
                  <div className="col-md-6">
                    <label className="form-label">{t('categories.type')}</label>
                    <div className="btn-group w-100" role="group" aria-label="Tipo de categoria">
                      <input
                        type="radio"
                        className="btn-check"
                        name="type"
                        id="income_cat"
                        value="income"
                        checked={formData.type === 'income'}
                        onChange={handleChange}
                        disabled={loading}
                      />
                      <label className="btn btn-outline-success" htmlFor="income_cat">
                        <i className="bi bi-arrow-up-circle me-2"></i>
                        {t('categories.income')}
                      </label>

                      <input
                        type="radio"
                        className="btn-check"
                        name="type"
                        id="expense_cat"
                        value="expense"
                        checked={formData.type === 'expense'}
                        onChange={handleChange}
                        disabled={loading}
                      />
                      <label className="btn btn-outline-danger" htmlFor="expense_cat">
                        <i className="bi bi-arrow-down-circle me-2"></i>
                        {t('categories.expense')}
                      </label>
                    </div>
                  </div>

                  {/* Cor */}
                  <div className="col-md-6">
                    <label className="form-label">{t('categories.color')}</label>
                    <div className="d-flex flex-wrap gap-2">
                      {availableColors.map((color) => (
                        <button
                          key={color}
                          type="button"
                          name={`color-${color}`}
                          aria-label={`Selecionar cor ${color}`}
                          className={`btn p-0 border ${formData.color === color ? 'border-dark border-3' : 'border-2'}`}
                          style={{
                            width: '40px',
                            height: '40px',
                            backgroundColor: color,
                            borderRadius: '50%'
                          }}
                          onClick={() => handleChange({ target: { name: 'color', value: color } })}
                          disabled={loading}
                        />
                      ))}
                    </div>
                    <input
                      type="color"
                      id="category-color"
                      name="color"
                      className="form-control form-control-color mt-2"
                      value={formData.color}
                      onChange={handleChange}
                      disabled={loading}
                      title="Escolher cor personalizada"
                      aria-label="Escolher cor personalizada"
                    />
                  </div>

                  {/* Ícone */}
                  <div className="col-12">
                    <label className="form-label">{t('categories.icon')}</label>
                    <div className="d-flex flex-wrap gap-2" role="group" aria-label="Selecionar ícone">
                      {availableIcons.map((icon) => (
                        <button
                          key={icon}
                          type="button"
                          name={`icon-${icon}`}
                          aria-label={`Selecionar ícone ${icon}`}
                          className={`btn btn-outline-secondary ${formData.icon === icon ? 'active' : ''}`}
                          style={{ width: '50px', height: '50px' }}
                          onClick={() => handleChange({ target: { name: 'icon', value: icon } })}
                          disabled={loading}
                        >
                          <i className={`bi bi-${icon}`}></i>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleClose}
                  disabled={loading}
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <span className="loading-spinner me-2"></span>
                      {t('common.loading')}
                    </>
                  ) : (
                    t('common.save')
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </>
  );
};

export default CategoryForm;