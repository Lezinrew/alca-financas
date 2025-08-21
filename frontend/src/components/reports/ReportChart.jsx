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

    // Gera cores adicionais se necessário
    const additionalColors = [
      '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
      '#FF9F40', '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384'
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
          borderColor: backgroundColors.map(color => color + 'CC'),
          borderWidth: 2,
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
      },
      tooltip: {
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
        ticks: {
          callback: function(value) {
            return 'R$ ' + value.toFixed(0).replace(/\d(?=(\d{3})+$)/g, '$&.');
          }
        }
      }
    } : {}
  };

  if (!chartData) {
    return (
      <div className="d-flex align-items-center justify-content-center" style={{ height: '300px' }}>
        <div className="text-center text-muted">
          <i className="bi bi-pie-chart display-4 mb-3"></i>
          <p>Nenhum dado para exibir</p>
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