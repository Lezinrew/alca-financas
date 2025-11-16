import React, { useMemo } from 'react';
import { Pie, Doughnut, Bar, Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
} from 'chart.js';

ChartJS.register(
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title
);

const ReportChart = ({ data, chartType, reportType }) => {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return null;

    const labels = data.map(item => item.category_name || item.account_name);
    const values = data.map(item => item.total || item.current_balance || 0);
    const colors = data.map(item => item.category_color || item.account_color);

    // Additional colors if needed
    const additionalColors = [
      '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
      '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#6366f1'
    ];

    const backgroundColors = colors.map((color, index) =>
      color || additionalColors[index % additionalColors.length]
    );

    return {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: backgroundColors,
          borderColor: '#ffffff',
          borderWidth: 2,
          hoverOffset: 4,
        },
      ],
    };
  }, [data]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: chartType === 'bar' || chartType === 'line',
        position: 'bottom',
        labels: {
          padding: 15,
          font: {
            size: 12,
            family: "'Inter', sans-serif",
          },
          usePointStyle: true,
        }
      },
      tooltip: {
        backgroundColor: '#1e293b',
        titleColor: '#f1f5f9',
        bodyColor: '#cbd5e1',
        padding: 12,
        cornerRadius: 8,
        displayColors: true,
        callbacks: {
          label: function(context) {
            const value = context.parsed || context.parsed.y;
            const total = context.dataset.data.reduce((a, b) => a + b, 0);
            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;

            return `${context.label}: R$ ${value.toFixed(2).replace('.', ',')} (${percentage}%)`;
          }
        }
      }
    },
    scales: chartType === 'bar' || chartType === 'line' ? {
      y: {
        beginAtZero: true,
        grid: {
          color: '#f1f5f9',
        },
        ticks: {
          font: {
            size: 11,
            family: "'Inter', sans-serif",
          },
          color: '#64748b',
          callback: function(value) {
            return 'R$ ' + value.toFixed(0).replace(/\d(?=(\d{3})+$)/g, '$&.');
          }
        }
      },
      x: {
        grid: {
          display: false,
        },
        ticks: {
          font: {
            size: 11,
            family: "'Inter', sans-serif",
          },
          color: '#64748b',
        }
      }
    } : {}
  };

  if (!chartData) {
    return (
      <div className="flex items-center justify-center" style={{ height: '300px' }}>
        <div className="text-center text-slate-400">
          <i className="bi bi-pie-chart text-6xl mb-3 block"></i>
          <p className="text-sm">Nenhum dado para exibir</p>
        </div>
      </div>
    );
  }

  const renderChart = () => {
    const chartProps = {
      data: chartData,
      options: chartOptions,
      height: 300
    };

    switch (chartType) {
      case 'pie':
        return <Pie {...chartProps} />;
      case 'doughnut':
        return <Doughnut {...chartProps} />;
      case 'bar':
        return <Bar {...chartProps} />;
      case 'line':
        return <Line {...chartProps} />;
      default:
        return <Pie {...chartProps} />;
    }
  };

  return (
    <div style={{ height: '300px', position: 'relative' }}>
      {renderChart()}
    </div>
  );
};

export default ReportChart;
