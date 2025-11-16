import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { dashboardAPI, formatCurrency } from '../api/client';
import type { DashboardData } from '../types';

export default function DashboardScreen() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      const response = await dashboardAPI.getData();
      setData(response.data);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  if (loading && !data) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#3b82f6" />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <View style={styles.header}>
        <Text style={styles.title}>Dashboard</Text>
        <Text style={styles.subtitle}>Visão geral das finanças</Text>
      </View>

      {/* KPI Cards */}
      <View style={styles.kpiContainer}>
        <View style={[styles.kpiCard, styles.balanceCard]}>
          <Text style={styles.kpiLabel}>Saldo Total</Text>
          <Text style={styles.kpiValue}>
            {formatCurrency(data?.total_balance || 0)}
          </Text>
        </View>

        <View style={styles.row}>
          <View style={[styles.kpiCard, styles.incomeCard]}>
            <Text style={styles.kpiLabel}>Receitas</Text>
            <Text style={[styles.kpiValue, styles.incomeText]}>
              {formatCurrency(data?.total_income || 0)}
            </Text>
          </View>

          <View style={[styles.kpiCard, styles.expenseCard]}>
            <Text style={styles.kpiLabel}>Despesas</Text>
            <Text style={[styles.kpiValue, styles.expenseText]}>
              {formatCurrency(data?.total_expense || 0)}
            </Text>
          </View>
        </View>

        <View style={[styles.kpiCard, styles.pendingCard]}>
          <Text style={styles.kpiLabel}>Pendências</Text>
          <Text style={styles.kpiValue}>
            {data?.pending_transactions || 0} transações
          </Text>
        </View>
      </View>

      {/* Recent Transactions */}
      {data?.recent_transactions && data.recent_transactions.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Transações Recentes</Text>
          {data.recent_transactions.slice(0, 5).map((transaction) => (
            <View key={transaction.id} style={styles.transactionItem}>
              <View style={styles.transactionInfo}>
                <Text style={styles.transactionDescription}>
                  {transaction.description}
                </Text>
                <Text style={styles.transactionDate}>
                  {new Date(transaction.date).toLocaleDateString('pt-BR')}
                </Text>
              </View>
              <Text
                style={[
                  styles.transactionAmount,
                  transaction.type === 'income'
                    ? styles.incomeText
                    : styles.expenseText,
                ]}
              >
                {transaction.type === 'income' ? '+' : '-'}
                {formatCurrency(transaction.amount)}
              </Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    padding: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#0f172a',
  },
  subtitle: {
    fontSize: 14,
    color: '#64748b',
    marginTop: 4,
  },
  kpiContainer: {
    padding: 16,
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  kpiCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  balanceCard: {
    backgroundColor: '#3b82f6',
  },
  incomeCard: {
    flex: 1,
    backgroundColor: '#10b981',
  },
  expenseCard: {
    flex: 1,
    backgroundColor: '#ef4444',
  },
  pendingCard: {
    backgroundColor: '#f59e0b',
  },
  kpiLabel: {
    fontSize: 12,
    color: '#fff',
    opacity: 0.9,
    marginBottom: 8,
    fontWeight: '500',
  },
  kpiValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
  },
  incomeText: {
    color: '#10b981',
  },
  expenseText: {
    color: '#ef4444',
  },
  section: {
    padding: 16,
    backgroundColor: '#fff',
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#0f172a',
    marginBottom: 16,
  },
  transactionItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  transactionInfo: {
    flex: 1,
  },
  transactionDescription: {
    fontSize: 14,
    fontWeight: '500',
    color: '#0f172a',
    marginBottom: 4,
  },
  transactionDate: {
    fontSize: 12,
    color: '#64748b',
  },
  transactionAmount: {
    fontSize: 16,
    fontWeight: '600',
  },
});
