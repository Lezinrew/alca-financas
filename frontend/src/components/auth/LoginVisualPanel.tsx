import React from 'react';
import DashboardMockup from './DashboardMockup';

/**
 * Painel institucional exibido ao lado do formulário de login (desktop/tablet).
 * Conteúdo de storytelling visual — puramente decorativo além da headline.
 */
const LoginVisualPanel: React.FC = () => {
  return (
    <div className="login-visual-panel">
      <div className="login-visual-panel__mesh" aria-hidden="true" />
      <div className="login-visual-panel__blob login-visual-panel__blob--1" aria-hidden="true" />
      <div className="login-visual-panel__blob login-visual-panel__blob--2" aria-hidden="true" />
      <div className="login-visual-panel__grid" aria-hidden="true" />

      <div className="login-visual-panel__content">
        <div className="login-visual-panel__brand login-stagger-1">
          <span className="login-logo-badge">
            <img
              src="/alcahub-logo.png"
              alt="Alça Finanças"
              className="login-visual-panel__logo"
            />
          </span>
        </div>

        <div className="login-visual-panel__copy login-stagger-2">
          <h1 className="login-visual-panel__headline">
            Sua vida financeira,
            <br />
            organizada em um só lugar.
          </h1>
          <p className="login-visual-panel__subtext">
            Visualize seus gastos, acompanhe suas metas e tome decisões com mais clareza.
          </p>
        </div>

        <div className="login-visual-panel__mockup login-stagger-3">
          <DashboardMockup />
        </div>
      </div>
    </div>
  );
};

export default LoginVisualPanel;
