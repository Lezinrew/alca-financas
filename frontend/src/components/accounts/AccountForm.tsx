import React, { useState, useEffect } from 'react';

// Type definitions
interface Account {
  id?: number;
  name: string;
  type: 'wallet' | 'checking' | 'savings' | 'credit_card' | 'investment';
  institution?: string;
  initial_balance: number;
  color: string;
  icon: string;
  is_active: boolean;
}

interface AccountFormData {
  name: string;
  type: 'wallet' | 'checking' | 'savings' | 'credit_card' | 'investment';
  institution: string;
  initial_balance: string;
  color: string;
  icon: string;
  is_active: boolean;
}

interface AccountFormProps {
  show: boolean;
  onHide: () => void;
  onSubmit: (account: Omit<Account, 'id'>) => Promise<void>;
  account?: Account | null;
}

interface AccountType {
  value: 'wallet' | 'checking' | 'savings' | 'credit_card' | 'investment';
  label: string;
  icon: string;
}

const AccountForm: React.FC<AccountFormProps> = ({ show, onHide, onSubmit, account }) => {
  const [formData, setFormData] = useState<AccountFormData>({
    name: '',
    type: 'wallet',
    institution: '',
    initial_balance: '',
    color: '#6366f1',
    icon: 'wallet2',
    is_active: true
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  const accountTypes: AccountType[] = [
    { value: 'wallet', label: 'Carteira', icon: 'wallet2' },
    { value: 'checking', label: 'Conta Corrente', icon: 'bank' },
    { value: 'savings', label: 'Poupança', icon: 'piggy-bank' },
    { value: 'credit_card', label: 'Cartão de Crédito', icon: 'credit-card' },
    { value: 'investment', label: 'Investimento', icon: 'graph-up-arrow' }
  ];

  const availableColors: string[] = [
    '#6366f1', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
    '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6b7280',
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57'
  ];

  const availableIcons: string[] = [
    'wallet2', 'bank', 'credit-card', 'piggy-bank', 'cash-coin',
    'currency-dollar', 'graph-up-arrow', 'briefcase', 'house',
    'car-front', 'phone', 'laptop', 'gift'
  ];

  // Preenche o formulário se estiver editando
  useEffect(() => {
    if (account) {
      setFormData({
        name: account.name || '',
        type: account.type || 'wallet',
        institution: account.institution || '',
        initial_balance: account.initial_balance?.toString() || '',
        color: account.color || '#6366f1',
        icon: account.icon || 'wallet2',
        is_active: account.is_active !== false
      });
    } else {
      // Reset form for new account
      setFormData({
        name: '',
        type: 'wallet',
        institution: '',
        initial_balance: '',
        color: '#6366f1',
        icon: 'wallet2',
        is_active: true
      });
    }
  }, [account]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement> | { target: { name: string; value: string | boolean; type?: string; checked?: boolean } }) => {
    const { name, value, type, checked } = e.target;
    
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    
    // Atualiza ícone automaticamente quando tipo muda
    if (name === 'type') {
      const typeConfig = accountTypes.find(t => t.value === value);
      if (typeConfig) {
        setFormData(prev => ({
          ...prev,
          icon: typeConfig.icon
        }));
      }
    }
    
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Validações
      if (!formData.name.trim()) {
        throw new Error('Nome da conta é obrigatório');
      }

      if (formData.initial_balance && isNaN(parseFloat(formData.initial_balance))) {
        throw new Error('Saldo inicial deve ser um número válido');
      }

      // Prepara dados para envio
      const submitData: Omit<Account, 'id'> = {
        name: formData.name.trim(),
        type: formData.type,
        institution: formData.institution.trim(),
        initial_balance: formData.initial_balance ? parseFloat(formData.initial_balance) : 0,
        color: formData.color,
        icon: formData.icon,
        is_active: formData.is_active
      };

      await onSubmit(submitData);
    } catch (err) {
      setError((err as Error).message || 'Erro ao salvar conta');
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
    <div className="modal fade show" style={{ display: 'block' }} tabIndex="-1" role="dialog">
      <div className="modal-backdrop fade show" onClick={handleClose}></div>
      <div className="modal-dialog modal-lg" role="document">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">
              {account ? 'Editar Conta' : 'Nova Conta'}
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

              {/* Preview da Conta */}
              <div className="text-center mb-4">
                <div 
                  className="rounded-circle d-inline-flex align-items-center justify-content-center mx-auto mb-2"
                  style={{
                    width: '80px',
                    height: '80px',
                    backgroundColor: formData.color,
                    color: 'white'
                  }}
                >
                  <i className={`bi bi-${formData.icon}`} style={{ fontSize: '2rem' }}></i>
                </div>
                <h5 className="mb-0">{formData.name || 'Nome da Conta'}</h5>
                <small className="text-muted">
                  {accountTypes.find(t => t.value === formData.type)?.label}
                </small>
              </div>

              <div className="row g-3">
                {/* Nome */}
                <div className="col-12">
                  <label className="form-label">Nome da Conta</label>
                  <input
                    type="text"
                    name="name"
                    className="form-control"
                    value={formData.name}
                    onChange={handleChange}
                    required
                    disabled={loading}
                    placeholder="Ex: Carteira Principal, Banco do Brasil"
                  />
                </div>

                {/* Tipo */}
                <div className="col-md-6">
                  <label className="form-label">Tipo de Conta</label>
                  <select
                    name="type"
                    className="form-select"
                    value={formData.type}
                    onChange={handleChange}
                    disabled={loading}
                  >
                    {accountTypes.map(type => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Saldo Inicial */}
                <div className="col-md-6">
                  <label className="form-label">Saldo Inicial</label>
                  <div className="input-group">
                    <span className="input-group-text">R$</span>
                    <input
                      type="number"
                      name="initial_balance"
                      className="form-control"
                      value={formData.initial_balance}
                      onChange={handleChange}
                      step="0.01"
                      disabled={loading}
                      placeholder="0,00"
                    />
                  </div>
                </div>

                {/* Instituição */}
                <div className="col-12">
                  <label className="form-label">Instituição (Opcional)</label>
                  <input
                    type="text"
                    name="institution"
                    className="form-control"
                    value={formData.institution}
                    onChange={handleChange}
                    disabled={loading}
                    placeholder="Ex: Banco do Brasil, Nubank, Caixa"
                  />
                </div>

                {/* Cor */}
                <div className="col-md-6">
                  <label className="form-label">Cor</label>
                  <div className="d-flex flex-wrap gap-2 mb-2">
                    {availableColors.map((color) => (
                      <button
                        key={color}
                        type="button"
                        className={`btn p-0 border ${formData.color === color ? 'border-dark border-3' : 'border-2'}`}
                        style={{
                          width: '32px',
                          height: '32px',
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
                    name="color"
                    className="form-control form-control-color"
                    value={formData.color}
                    onChange={handleChange}
                    disabled={loading}
                  />
                </div>

                {/* Ícone */}
                <div className="col-md-6">
                  <label className="form-label">Ícone</label>
                  <div className="d-flex flex-wrap gap-1">
                    {availableIcons.map((icon) => (
                      <button
                        key={icon}
                        type="button"
                        className={`btn btn-outline-secondary btn-sm ${formData.icon === icon ? 'active' : ''}`}
                        style={{ width: '40px', height: '40px' }}
                        onClick={() => handleChange({ target: { name: 'icon', value: icon } })}
                        disabled={loading}
                      >
                        <i className={`bi bi-${icon}`}></i>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Status Ativo */}
                <div className="col-12">
                  <div className="form-check">
                    <input
                      type="checkbox"
                      name="is_active"
                      className="form-check-input"
                      id="is_active"
                      checked={formData.is_active}
                      onChange={handleChange}
                      disabled={loading}
                    />
                    <label className="form-check-label" htmlFor="is_active">
                      Conta ativa
                    </label>
                    <div className="form-text">
                      Contas inativas não aparecem nos relatórios
                    </div>
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
                Cancelar
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <span className="loading-spinner me-2"></span>
                    Salvando...
                  </>
                ) : (
                  <>
                    <i className="bi bi-check me-2"></i>
                    Salvar
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AccountForm;