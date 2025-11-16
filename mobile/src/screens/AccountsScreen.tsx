import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { accountsAPI, formatCurrency } from '../api/client';
import type { Account } from '../types';

export default function AccountsScreen() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadAccounts = async () => {
    try {
      setLoading(true);
      const response = await accountsAPI.getAll();
      setAccounts(response.data);
    } catch (error) {
      console.error('Error loading accounts:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadAccounts();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadAccounts();
  };

  const getAccountTypeLabel = (type: Account['type']) => {
    const labels = {
      wallet: 'Carteira',
      checking: 'Conta Corrente',
      savings: 'Poupança',
      credit_card: 'Cartão de Crédito',
      investment: 'Investimento',
    };
    return labels[type];
  };

  const renderAccount = ({ item }: { item: Account }) => (
    <View style={[styles.accountCard, { borderLeftColor: item.color }]}>
      <View style={styles.accountHeader}>
        <View
          style={[styles.accountIcon, { backgroundColor: item.color }]}
        >
          <Text style={styles.iconText}>{item.icon || '💳'}</Text>
        </View>
        <View style={styles.accountInfo}>
          <Text style={styles.accountName}>{item.name}</Text>
          <Text style={styles.accountType}>
            {getAccountTypeLabel(item.type)}
          </Text>
          {item.institution && (
            <Text style={styles.institution}>{item.institution}</Text>
          )}
        </View>
      </View>

      <View style={styles.balanceContainer}>
        <Text style={styles.balanceLabel}>Saldo Atual</Text>
        <Text
          style={[
            styles.balance,
            item.current_balance >= 0
              ? styles.positiveBalance
              : styles.negativeBalance,
          ]}
        >
          {formatCurrency(item.current_balance)}
        </Text>
      </View>

      <View style={styles.statusContainer}>
        <View
          style={[
            styles.statusBadge,
            item.is_active ? styles.activeStatus : styles.inactiveStatus,
          ]}
        >
          <Text style={styles.statusText}>
            {item.is_active ? 'Ativa' : 'Inativa'}
          </Text>
        </View>
      </View>
    </View>
  );

  const totalBalance = accounts.reduce(
    (sum, account) => sum + account.current_balance,
    0
  );

  if (loading && accounts.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#3b82f6" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Contas</Text>
        <Text style={styles.subtitle}>
          {accounts.length} conta{accounts.length !== 1 ? 's' : ''}
        </Text>
      </View>

      <View style={styles.totalCard}>
        <Text style={styles.totalLabel}>Saldo Total</Text>
        <Text style={styles.totalValue}>{formatCurrency(totalBalance)}</Text>
      </View>

      <FlatList
        data={accounts}
        renderItem={renderAccount}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Nenhuma conta cadastrada</Text>
          </View>
        }
      />
    </View>
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
  totalCard: {
    margin: 16,
    padding: 20,
    backgroundColor: '#3b82f6',
    borderRadius: 12,
  },
  totalLabel: {
    fontSize: 12,
    color: '#fff',
    opacity: 0.9,
    marginBottom: 8,
  },
  totalValue: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#fff',
  },
  list: {
    padding: 16,
    paddingTop: 0,
  },
  accountCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  accountHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  accountIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  iconText: {
    fontSize: 24,
  },
  accountInfo: {
    flex: 1,
  },
  accountName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#0f172a',
    marginBottom: 4,
  },
  accountType: {
    fontSize: 12,
    color: '#64748b',
    marginBottom: 2,
  },
  institution: {
    fontSize: 11,
    color: '#94a3b8',
  },
  balanceContainer: {
    marginBottom: 12,
  },
  balanceLabel: {
    fontSize: 11,
    color: '#64748b',
    marginBottom: 4,
  },
  balance: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  positiveBalance: {
    color: '#10b981',
  },
  negativeBalance: {
    color: '#ef4444',
  },
  statusContainer: {
    flexDirection: 'row',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  activeStatus: {
    backgroundColor: '#d1fae5',
  },
  inactiveStatus: {
    backgroundColor: '#f1f5f9',
  },
  statusText: {
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  emptyContainer: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 14,
    color: '#94a3b8',
  },
});
