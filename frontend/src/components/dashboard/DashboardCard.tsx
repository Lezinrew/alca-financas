interface DashboardCardProps {
  title: string;
  value: string;
  icon: string;
  type?: 'income' | 'expense' | 'balance' | string;
  subtitle?: string;
}

const DashboardCard: React.FC<DashboardCardProps> = ({ title, value, icon, type, subtitle }) => {
  const getCardClass = () => {
    switch (type) {
      case 'income':
        return 'dashboard-card income';
      case 'expense':
        return 'dashboard-card expense';
      case 'balance':
        return 'dashboard-card balance';
      default:
        return 'dashboard-card';
    }
  };

  return (
    <div className={`card ${getCardClass()}`}>
      <div className="card-body d-flex align-items-center">
        <div className="card-icon me-3">
          <i className={icon}></i>
        </div>
        
        <div className="flex-grow-1">
          <h6 className="card-title text-muted mb-1">{title}</h6>
          <h4 className="card-value mb-0">{value}</h4>
          {subtitle && (
            <small className="text-muted">{subtitle}</small>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardCard;