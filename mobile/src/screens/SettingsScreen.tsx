import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';

export default function SettingsScreen() {
  const settingsOptions = [
    { id: '1', title: 'Perfil', icon: '👤', screen: 'profile' },
    { id: '2', title: 'Notificações', icon: '🔔', screen: 'notifications' },
    { id: '3', title: 'Segurança', icon: '🔒', screen: 'security' },
    { id: '4', title: 'Moeda', icon: '💰', screen: 'currency' },
    { id: '5', title: 'Idioma', icon: '🌐', screen: 'language' },
    { id: '6', title: 'Tema', icon: '🎨', screen: 'theme' },
    { id: '7', title: 'Sobre', icon: 'ℹ️', screen: 'about' },
    { id: '8', title: 'Sair', icon: '🚪', screen: 'logout', destructive: true },
  ];

  const handlePress = (screen: string) => {
    console.log('Navigate to:', screen);
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Configurações</Text>
        <Text style={styles.subtitle}>Ajuste suas preferências</Text>
      </View>

      <ScrollView style={styles.scrollView}>
        <View style={styles.section}>
          {settingsOptions.map((option) => (
            <TouchableOpacity
              key={option.id}
              style={[
                styles.optionItem,
                option.destructive && styles.destructiveOption,
              ]}
              onPress={() => handlePress(option.screen)}
              activeOpacity={0.7}
            >
              <Text style={styles.optionIcon}>{option.icon}</Text>
              <Text
                style={[
                  styles.optionTitle,
                  option.destructive && styles.destructiveText,
                ]}
              >
                {option.title}
              </Text>
              <Text style={styles.chevron}>›</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.footer}>
          <Text style={styles.version}>Alça Finanças v1.0.0</Text>
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
  scrollView: {
    flex: 1,
  },
  section: {
    margin: 16,
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    overflow: 'hidden',
  },
  optionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  destructiveOption: {
    borderBottomWidth: 0,
  },
  optionIcon: {
    fontSize: 20,
    marginRight: 12,
  },
  optionTitle: {
    flex: 1,
    fontSize: 16,
    color: '#0f172a',
  },
  destructiveText: {
    color: '#ef4444',
  },
  chevron: {
    fontSize: 24,
    color: '#cbd5e1',
    fontWeight: '300',
  },
  footer: {
    padding: 20,
    alignItems: 'center',
  },
  version: {
    fontSize: 12,
    color: '#94a3b8',
  },
});
