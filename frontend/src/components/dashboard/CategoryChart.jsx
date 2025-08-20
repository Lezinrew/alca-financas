import React from 'react';
import { useTranslation } from 'react-i18next';
import { formatCurrency } from '../../utils/api';

const CategoryChart = ({ data, type }) => {
  const { t } = useTranslation();

  if (!data || data.length === 0) {
    return (
      <div className="text-center text-muted py-4">
        <i className="bi bi-pie-chart display-4 d-block mb-3"></i>
        <p className="mb-0">Nenhuma categoria encontrada</p>
      </div>
    );
  }

  // Calcula o total para as porcentagens
  const total = data.reduce((acc, item) => acc + item.total, 0);

  return (
    <div className="category-chart">
      {/* Gráfico de barras simples */}
      <div className="mb-4">
        {data.slice(0, 5).map((category, index) => {
          const percentage = total > 0 ? (category.total / total) * 100 : 0;
          
          return (
            <div key={category.category_id} className="mb-3">
              <div className="d-flex justify-content-between align-items-center mb-1">
                <div className="d-flex align-items-center">
                  <div 
                    className="rounded-circle me-2"
                    style={{
                      width: '12px',
                      height: '12px',
                      backgroundColor: category.category_color
                    }}
                  ></div>
                  <small className="text-muted">{category.category_name}</small>
                </div>
                <small className="fw-bold">
                  {formatCurrency(category.total)} ({percentage.toFixed(1)}%)
                </small>
              </div>
              
              <div className="progress" style={{ height: '8px' }}>
                <div
                  className="progress-bar"
                  role="progressbar"
                  style={{
                    width: `${percentage}%`,
                    backgroundColor: category.category_color
                  }}
                  aria-valuenow={percentage}
                  aria-valuemin="0"
                  aria-valuemax="100"
                ></div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Resumo */}
      <div className="row text-center">
        <div className="col-4">
          <div className="text-muted small">Categorias</div>
          <div className="fw-bold">{data.length}</div>
        </div>
        <div className="col-4">
          <div className="text-muted small">Total</div>
          <div className="fw-bold">{formatCurrency(total)}</div>
        </div>
        <div className="col-4">
          <div className="text-muted small">Transações</div>
          <div className="fw-bold">
            {data.reduce((acc, item) => acc + item.count, 0)}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CategoryChart;