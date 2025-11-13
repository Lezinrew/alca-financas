
const ReportFilters = ({ filters, onFilterChange }) => {
  const months = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ];

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 5 }, (_, i) => currentYear - 2 + i);

  const handlePrevMonth = () => {
    if (filters.month === 1) {
      onFilterChange('month', 12);
      onFilterChange('year', filters.year - 1);
    } else {
      onFilterChange('month', filters.month - 1);
    }
  };

  const handleNextMonth = () => {
    if (filters.month === 12) {
      onFilterChange('month', 1);
      onFilterChange('year', filters.year + 1);
    } else {
      onFilterChange('month', filters.month + 1);
    }
  };

  return (
    <div className="d-flex align-items-center gap-2">
      {/* Navegação de Mês */}
      <button 
        className="btn btn-outline-secondary btn-sm"
        onClick={handlePrevMonth}
      >
        <i className="bi bi-chevron-left"></i>
      </button>
      
      <div className="d-flex align-items-center">
        <div className="bg-primary text-white px-3 py-1 rounded">
          {months[filters.month - 1]} {filters.year}
        </div>
      </div>
      
      <button 
        className="btn btn-outline-secondary btn-sm"
        onClick={handleNextMonth}
      >
        <i className="bi bi-chevron-right"></i>
      </button>

      {/* Dropdown para seleção rápida */}
      <div className="dropdown ms-2">
        <button 
          className="btn btn-outline-secondary btn-sm dropdown-toggle" 
          type="button" 
          data-bs-toggle="dropdown"
        >
          <i className="bi bi-calendar3"></i>
        </button>
        <ul className="dropdown-menu">
          <li><h6 className="dropdown-header">Selecionar Mês</h6></li>
          {months.map((month, index) => (
            <li key={index}>
              <button 
                className={`dropdown-item ${filters.month === index + 1 ? 'active' : ''}`}
                onClick={() => onFilterChange('month', index + 1)}
              >
                {month}
              </button>
            </li>
          ))}
          <li><hr className="dropdown-divider" /></li>
          <li><h6 className="dropdown-header">Selecionar Ano</h6></li>
          {years.map(year => (
            <li key={year}>
              <button 
                className={`dropdown-item ${filters.year === year ? 'active' : ''}`}
                onClick={() => onFilterChange('year', year)}
              >
                {year}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default ReportFilters;