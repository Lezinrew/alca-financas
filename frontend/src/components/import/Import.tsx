import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { transactionsAPI, categoriesAPI } from '../../utils/api';

const Import = () => {
  const { t } = useTranslation();
  const [categories, setCategories] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [importResult, setImportResult] = useState(null);

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    try {
      const response = await categoriesAPI.getAll();
      setCategories(response.data);
    } catch (err) {
      console.error('Load categories error:', err);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setSelectedFile(file);
    setError('');
    setSuccess('');
    setImportResult(null);
  };

  const handleImport = async () => {
    if (!selectedFile) {
      setError('Selecione um arquivo CSV');
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
      setError('Apenas arquivos CSV são aceitos');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await transactionsAPI.import(selectedFile);
      setImportResult(response.data);
      
      if (response.data.imported_count > 0) {
        setSuccess(`${response.data.imported_count} transações importadas com sucesso!`);
      }
      
      // Limpa o arquivo selecionado
      setSelectedFile(null);
      document.getElementById('csvFile').value = '';
      
    } catch (err) {
      setError(err.response?.data?.error || 'Erro ao importar arquivo');
      setImportResult(err.response?.data);
    } finally {
      setLoading(false);
    }
  };

  const downloadSample = () => {
    const sampleData = [
      'description,amount,type,category_name,date',
      'Supermercado ABC,150.50,expense,Alimentação,2025-08-15',
      'Salário Mensal,3000.00,income,Salário,2025-08-01',
      'Gasolina Posto XYZ,80.00,expense,Transporte,2025-08-10',
      'Freelance Projeto,500.00,income,Freelance,2025-08-05'
    ].join('\n');

    const blob = new Blob([sampleData], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'exemplo_importacao_mobills.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="import">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="h3 mb-0">{t('import.title')}</h2>
      </div>

      <div className="row">
        <div className="col-lg-8">
          {/* Área de Upload */}
          <div className="card mb-4">
            <div className="card-header">
              <h5 className="card-title mb-0">
                <i className="bi bi-upload me-2"></i>
                Importar Arquivo CSV
              </h5>
            </div>
            <div className="card-body">
              {error && (
                <div className="alert alert-danger" role="alert">
                  <i className="bi bi-exclamation-triangle-fill me-2"></i>
                  {error}
                </div>
              )}

              {success && (
                <div className="alert alert-success" role="alert">
                  <i className="bi bi-check-circle-fill me-2"></i>
                  {success}
                </div>
              )}

              <div className="row g-3">
                <div className="col-12">
                  <label className="form-label">
                    <i className="bi bi-file-earmark-spreadsheet me-2"></i>
                    Selecionar Arquivo CSV
                  </label>
                  <input
                    type="file"
                    id="csvFile"
                    className="form-control"
                    accept=".csv"
                    onChange={handleFileChange}
                    disabled={loading}
                  />
                  <div className="form-text">
                    {t('import.requiredColumns')}
                  </div>
                </div>

                {selectedFile && (
                  <div className="col-12">
                    <div className="alert alert-info">
                      <i className="bi bi-info-circle me-2"></i>
                      <strong>Arquivo selecionado:</strong> {selectedFile.name} 
                      ({(selectedFile.size / 1024).toFixed(2)} KB)
                    </div>
                  </div>
                )}

                <div className="col-12">
                  <div className="d-flex gap-2">
                    <button
                      onClick={handleImport}
                      className="btn btn-primary"
                      disabled={!selectedFile || loading}
                    >
                      {loading ? (
                        <>
                          <span className="loading-spinner me-2"></span>
                          Importando...
                        </>
                      ) : (
                        <>
                          <i className="bi bi-upload me-2"></i>
                          {t('import.uploadFile')}
                        </>
                      )}
                    </button>

                    <button
                      onClick={downloadSample}
                      className="btn btn-outline-secondary"
                      disabled={loading}
                    >
                      <i className="bi bi-download me-2"></i>
                      Baixar Exemplo
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Resultado da Importação */}
          {importResult && (
            <div className="card mb-4">
              <div className="card-header">
                <h5 className="card-title mb-0">
                  <i className="bi bi-clipboard-data me-2"></i>
                  Resultado da Importação
                </h5>
              </div>
              <div className="card-body">
                <div className="row text-center mb-3">
                  <div className="col-md-4">
                    <div className="bg-success rounded p-3 text-white">
                      <i className="bi bi-check-circle display-6 mb-2"></i>
                      <h4>{importResult.imported_count || 0}</h4>
                      <small>Importadas</small>
                    </div>
                  </div>
                  <div className="col-md-4">
                    <div className="bg-danger rounded p-3 text-white mt-3 mt-md-0">
                      <i className="bi bi-x-circle display-6 mb-2"></i>
                      <h4>{importResult.error_count || 0}</h4>
                      <small>Erros</small>
                    </div>
                  </div>
                  <div className="col-md-4">
                    <div className="bg-info rounded p-3 text-white mt-3 mt-md-0">
                      <i className="bi bi-file-text display-6 mb-2"></i>
                      <h4>{(importResult.imported_count || 0) + (importResult.error_count || 0)}</h4>
                      <small>Total</small>
                    </div>
                  </div>
                </div>

                {importResult.errors && importResult.errors.length > 0 && (
                  <div>
                    <h6 className="text-danger mb-3">
                      <i className="bi bi-exclamation-triangle me-2"></i>
                      Erros Encontrados:
                    </h6>
                    <div className="alert alert-warning">
                      <ul className="mb-0">
                        {importResult.errors.slice(0, 10).map((error, index) => (
                          <li key={index} className="small">{error}</li>
                        ))}
                        {importResult.errors.length > 10 && (
                          <li className="small text-muted">
                            ... e mais {importResult.errors.length - 10} erros
                          </li>
                        )}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar com Instruções */}
        <div className="col-lg-4">
          <div className="card mb-4">
            <div className="card-header">
              <h6 className="card-title mb-0">
                <i className="bi bi-info-circle me-2"></i>
                Como Importar
              </h6>
            </div>
            <div className="card-body">
              <ol className="mb-3">
                <li className="mb-2">Prepare seu arquivo CSV com as colunas obrigatórias</li>
                <li className="mb-2">Selecione o arquivo usando o botão acima</li>
                <li className="mb-2">Clique em "Enviar arquivo" para iniciar a importação</li>
                <li>Verifique o resultado e corrija eventuais erros</li>
              </ol>

              <div className="alert alert-info">
                <i className="bi bi-lightbulb me-2"></i>
                <small>
                  <strong>Dica:</strong> Baixe o arquivo de exemplo para ver o formato correto.
                </small>
              </div>
            </div>
          </div>

          <div className="card mb-4">
            <div className="card-header">
              <h6 className="card-title mb-0">
                <i className="bi bi-table me-2"></i>
                Colunas Obrigatórias
              </h6>
            </div>
            <div className="card-body">
              <ul className="list-unstyled">
                <li className="mb-2">
                  <code>description</code> - Descrição da transação
                </li>
                <li className="mb-2">
                  <code>amount</code> - Valor (sempre positivo)
                </li>
                <li className="mb-2">
                  <code>type</code> - Tipo: income ou expense
                </li>
                <li className="mb-2">
                  <code>category_name</code> - Nome da categoria
                </li>
                <li>
                  <code>date</code> - Data (YYYY-MM-DD)
                </li>
              </ul>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h6 className="card-title mb-0">
                <i className="bi bi-tags me-2"></i>
                Categorias Disponíveis
              </h6>
            </div>
            <div className="card-body">
              <div className="row">
                <div className="col-12 mb-3">
                  <h6 className="text-success small">
                    <i className="bi bi-arrow-up-circle me-1"></i>
                    Receitas:
                  </h6>
                  <div className="d-flex flex-wrap gap-1">
                    {categories
                      .filter(cat => cat.type === 'income')
                      .map(cat => (
                        <span key={cat.id} className="badge bg-success-subtle text-success">
                          {cat.name}
                        </span>
                      ))
                    }
                  </div>
                </div>

                <div className="col-12">
                  <h6 className="text-danger small">
                    <i className="bi bi-arrow-down-circle me-1"></i>
                    Despesas:
                  </h6>
                  <div className="d-flex flex-wrap gap-1">
                    {categories
                      .filter(cat => cat.type === 'expense')
                      .map(cat => (
                        <span key={cat.id} className="badge bg-danger-subtle text-danger">
                          {cat.name}
                        </span>
                      ))
                    }
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Import;