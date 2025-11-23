import React from 'react';

interface ReportFiltersProps {
  filters: {
    month: number;
    year: number;
  };
  onFilterChange: (field: 'month' | 'year', value: number) => void;
}

const ReportFilters: React.FC<ReportFiltersProps> = ({ filters, onFilterChange }) => {
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
    <div className="flex items-center gap-3">
      {/* Navigation Buttons */}
      <button
        className="p-2.5 text-slate-600 dark:text-slate-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 hover:text-blue-600 dark:hover:text-blue-400 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
        onClick={handlePrevMonth}
        title="Mês anterior"
      >
        <i className="bi bi-chevron-left text-lg"></i>
      </button>

      {/* Current Period Display */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 dark:from-blue-500 dark:to-indigo-500 text-white px-6 py-2.5 rounded-lg font-bold text-sm shadow-md">
        {months[filters.month - 1]} {filters.year}
      </div>

      <button
        className="p-2.5 text-slate-600 dark:text-slate-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 hover:text-blue-600 dark:hover:text-blue-400 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
        onClick={handleNextMonth}
        title="Próximo mês"
      >
        <i className="bi bi-chevron-right text-lg"></i>
      </button>

      {/* Quick Select Dropdown */}
      <div className="relative group">
        <button
          className="p-2.5 text-slate-600 dark:text-slate-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 hover:text-blue-600 dark:hover:text-blue-400 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
          type="button"
          title="Selecionar período"
        >
          <i className="bi bi-calendar3 text-lg"></i>
        </button>

        {/* Dropdown Menu */}
        <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-[#1a1d29] rounded-xl shadow-xl border border-slate-200 dark:border-slate-700/50 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-10 max-h-96 overflow-y-auto custom-scrollbar">
          {/* Months */}
          <div className="p-2 border-b border-slate-200">
            <div className="px-3 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Selecionar Mês</div>
            <div className="space-y-1">
              {months.map((month, index) => (
                <button
                  key={index}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    filters.month === index + 1
                      ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                      : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                  }`}
                  onClick={() => onFilterChange('month', index + 1)}
                >
                  {month}
                </button>
              ))}
            </div>
          </div>

          {/* Years */}
          <div className="p-2">
            <div className="px-3 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Selecionar Ano</div>
            <div className="space-y-1">
              {years.map(year => (
                <button
                  key={year}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    filters.year === year
                      ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                      : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                  }`}
                  onClick={() => onFilterChange('year', year)}
                >
                  {year}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportFilters;
