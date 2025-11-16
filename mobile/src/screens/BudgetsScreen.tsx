import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';

export default function BudgetsScreen() {
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Orçamentos</Text>
        <Text style={styles.subtitle}>Em desenvolvimento</Text>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.placeholder}>
          <Text style={styles.placeholderIcon}>📊</Text>
          <Text style={styles.placeholderTitle}>Orçamentos</Text>
          <Text style={styles.placeholderText}>
            Funcionalidade em desenvolvimento.{'\n'}
            Em breve você poderá gerenciar seus orçamentos por aqui.
          </Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
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
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  placeholder: {
    alignItems: 'center',
  },
  placeholderIcon: {
    fontSize: 64,
    marginBottom: 16,
  },
  placeholderTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#0f172a',
    marginBottom: 8,
  },
  placeholderText: {
    fontSize: 14,
    color: '#64748b',
    textAlign: 'center',
    lineHeight: 20,
  },
});
