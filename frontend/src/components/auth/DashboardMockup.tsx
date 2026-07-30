import React from 'react';
import { TrendingUp, ArrowUpRight, PiggyBank, Briefcase, Home, LineChart } from 'lucide-react';

const transactions = [
  { label: 'Salário', value: '+ R$ 8.200,00', type: 'income' as const, icon: Briefcase },
  { label: 'Aluguel', value: '- R$ 2.100,00', type: 'expense' as const, icon: Home },
  { label: 'Investimentos', value: '+ R$ 1.350,00', type: 'income' as const, icon: LineChart },
];

/**
 * Ilustração decorativa e fictícia de um dashboard financeiro.
 * Puramente visual — nenhum dado real é exibido aqui.
 */
const DashboardMockup: React.FC = () => {
  return (
    <div className="login-dashboard-preview" aria-hidden="true">
      <div className="login-dashboard-preview__badge login-dashboard-preview__badge--top">
        <TrendingUp className="h-3.5 w-3.5" />
        <span>Receitas +18%</span>
      </div>

      <div className="login-dashboard-preview__card">
        <div className="login-dashboard-preview__card-header">
          <span className="login-dashboard-preview__label">Saldo atual</span>
          <span className="login-dashboard-preview__delta">
            <ArrowUpRight className="h-3 w-3" />
            12,4%
          </span>
        </div>
        <div className="login-dashboard-preview__balance">R$ 24.850,00</div>

        <svg
          viewBox="0 0 240 64"
          className="login-dashboard-preview__chart"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="loginChartFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--login-chart-line)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="var(--login-chart-line)" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M0,48 C20,44 32,50 48,40 C64,30 76,38 96,28 C116,18 128,30 148,22 C168,14 184,24 204,14 C218,7 228,12 240,4"
            fill="none"
            stroke="var(--login-chart-line)"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          <path
            d="M0,48 C20,44 32,50 48,40 C64,30 76,38 96,28 C116,18 128,30 148,22 C168,14 184,24 204,14 C218,7 228,12 240,4 L240,64 L0,64 Z"
            fill="url(#loginChartFill)"
            stroke="none"
          />
        </svg>

        <div className="login-dashboard-preview__transactions">
          {transactions.map(({ label, value, type, icon: Icon }) => (
            <div key={label} className="login-dashboard-preview__transaction">
              <span className="login-dashboard-preview__transaction-icon">
                <Icon className="h-3.5 w-3.5" />
              </span>
              <span className="login-dashboard-preview__transaction-label">{label}</span>
              <span
                className={`login-dashboard-preview__transaction-value login-dashboard-preview__transaction-value--${type}`}
              >
                {value}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="login-dashboard-preview__badge login-dashboard-preview__badge--bottom">
        <PiggyBank className="h-3.5 w-3.5" />
        <span>Economia R$ 3.240</span>
      </div>
    </div>
  );
};

export default DashboardMockup;
