import React from 'react';
import { formatCurrency } from '../../utils/api';

const AccountCard = ({ account, onEdit, onDelete }) => {
  const getAccountTypeIcon = (type) => {
    switch (type) {
      case 'wallet':
        return 'bi-wallet2';
      case 'checking':
        return 'bi-bank';
      case 'savings':
        return 'bi-piggy-bank';
      case 'credit_card':
        return 'bi-credit-card';
      case 'investment':
        return 'bi-graph-up-arrow';
      default:
        return 'bi-wallet2';
    }
  };

  const getAccountTypeName = (type) => {
    switch (type) {
      case 'wallet':
        return 'Carteira';
      case 'checking':
        return 'Conta Corrente';
      case 'savings':
        return 'Poupança';
      case 'credit_card':
        return 'Cartão de Crédito';
      case 'investment':
        return 'Investimento';
      default:
        return 'Conta';
    }
  };

  const getBalanceColor = () => {
    if (account.current_balance > 0) {
      return 'text-success';
    } else if (account.current_balance < 0) {
      return 'text-danger';
    }
    return 'text-muted';
  };

  return (
    <div className="card account-card h-100" style={{ borderLeft: `4px solid ${account.color}` }}>
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-start mb-3">
          <div className="d-flex align-items-center">
            <div 
              className="rounded-circle d-flex align-items-center justify-content-center me-3"
              style={{
                width: '40px',
                height: '40px',
                backgroundColor: account.color,
                color: 'white'
              }}
            >
              <i className={`bi ${account.icon || getAccountTypeIcon(account.type)}`}></i>
            </div>
            <div>
              <h6 className="card-title mb-0">{account.name}</h6>
              <small className="text-muted">{getAccountTypeName(account.type)}</small>
            </div>
          </div>
          
          <div className="dropdown">
            <button
              className="btn btn-link btn-sm text-muted p-0"
              type="button"
              data-bs-toggle="dropdown"
            >
              <i className="bi bi-three-dots-vertical"></i>
            </button>
            <ul className="dropdown-menu dropdown-menu-end">
              <li>
                <button 
                  className="dropdown-item" 
                  onClick={() => onEdit(account)}
                >
                  <i className="bi bi-pencil me-2"></i>
                  Editar
                </button>
              </li>
              <li><hr className="dropdown-divider" /></li>
              <li>
                <button 
                  className="dropdown-item text-danger" 
                  onClick={() => onDelete(account.id)}
                >
                  <i className="bi bi-trash me-2"></i>
                  Excluir
                </button>
              </li>
            </ul>
          </div>
        </div>

        {/* Instituição */}
        {account.institution && (
          <div className="mb-3">
            <small className="text-muted">Instituição:</small>
            <div>{account.institution}</div>
          </div>
        )}

        {/* Saldo */}
        <div className="mb-3">
          <small className="text-muted">Saldo Atual:</small>
          <div className={`h5 mb-0 ${getBalanceColor()}`}>
            {formatCurrency(account.current_balance || 0)}
          </div>
        </div>

        {/* Saldo Inicial vs Atual */}
        {account.initial_balance !== account.current_balance && (
          <div className="row text-center">
            <div className="col-6">
              <small className="text-muted">Inicial</small>
              <div className="fw-bold">
                {formatCurrency(account.initial_balance || 0)}
              </div>
            </div>
            <div className="col-6">
              <small className="text-muted">Variação</small>
              <div className={`fw-bold ${
                (account.current_balance - account.initial_balance) >= 0 ? 'text-success' : 'text-danger'
              }`}>
                {(account.current_balance - account.initial_balance) >= 0 ? '+' : ''}
                {formatCurrency((account.current_balance || 0) - (account.initial_balance || 0))}
              </div>
            </div>
          </div>
        )}

        {/* Status */}
        <div className="mt-3">
          <span className={`badge ${account.is_active ? 'bg-success' : 'bg-secondary'}`}>
            {account.is_active ? 'Ativa' : 'Inativa'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default AccountCard;