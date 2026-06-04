import React from 'react';
import {
  StyleSheet,
  View,
  Text,
  Modal,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Staff } from '../types';
import { COLORS } from '../theme/colors';

interface StaffPickerSheetProps {
  visible: boolean;
  onClose: () => void;
  onSelect: (emailOrDisplayName: string, displayName: string) => void;
  currentStaffId: string | null;
  staff: Staff[];
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export const StaffPickerSheet: React.FC<StaffPickerSheetProps> = ({
  visible,
  onClose,
  onSelect,
  currentStaffId,
  staff,
  isLoading,
  error,
  onRefresh,
}) => {
  const renderStaffItem = ({ item }: { item: Staff }) => {
    // Identifier used as worker_id in assignment payload
    const workerIdentifier = item.email || item.display_name || item.name;
    const isSelected = currentStaffId === workerIdentifier;
    const displayName = item.display_name || item.name || item.email;

    return (
      <TouchableOpacity
        style={[styles.itemRow, isSelected && styles.itemRowSelected]}
        onPress={() => onSelect(workerIdentifier, displayName)}
        activeOpacity={0.7}
      >
        <View style={styles.itemLeft}>
          <Text style={[styles.itemName, isSelected && styles.itemNameSelected]}>
            {displayName}
          </Text>
          <Text style={styles.itemEmail}>{item.email}</Text>
        </View>
        {isSelected && <Text style={styles.selectedCheck}>✓</Text>}
      </TouchableOpacity>
    );
  };

  return (
    <Modal
      transparent
      animationType="slide"
      visible={visible}
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <SafeAreaView style={styles.sheetContainer}>
          <View style={styles.header}>
            <Text style={styles.title}>Select Staff Member</Text>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn} activeOpacity={0.7}>
              <Text style={styles.closeBtnText}>Close</Text>
            </TouchableOpacity>
          </View>

          {isLoading ? (
            <View style={styles.centerContainer}>
              <ActivityIndicator color={COLORS.primary} size="large" />
              <Text style={styles.statusText}>Loading staff list...</Text>
            </View>
          ) : error ? (
            <View style={styles.centerContainer}>
              <Text style={styles.errorIcon}>⚠️</Text>
              <Text style={styles.errorText}>{error}</Text>
              <TouchableOpacity style={styles.retryBtn} onPress={onRefresh} activeOpacity={0.7}>
                <Text style={styles.retryText}>Retry Loading</Text>
              </TouchableOpacity>
            </View>
          ) : staff.length === 0 ? (
            <View style={styles.centerContainer}>
              <Text style={styles.emptyIcon}>👤</Text>
              <Text style={styles.emptyText}>No assignable staff found.</Text>
            </View>
          ) : (
            <FlatList
              data={staff}
              keyExtractor={(item) => item.staff_id}
              renderItem={renderStaffItem}
              contentContainerStyle={styles.listContent}
              showsVerticalScrollIndicator={false}
            />
          )}
        </SafeAreaView>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.4)',
    justifyContent: 'flex-end',
  },
  sheetContainer: {
    backgroundColor: COLORS.cardBg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '80%',
    minHeight: '40%',
    shadowColor: COLORS.text,
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 10,
    borderTopWidth: 1,
    borderTopColor: COLORS.borderSoft,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 18,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
  },
  title: {
    fontSize: 18,
    fontWeight: '800',
    color: COLORS.text,
  },
  closeBtn: {
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  closeBtnText: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.primary,
  },
  listContent: {
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  itemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 8,
    marginBottom: 8,
    backgroundColor: COLORS.background,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
  },
  itemRowSelected: {
    backgroundColor: '#edf2ee',
    borderColor: '#c9d9cc',
  },
  itemLeft: {
    flex: 1,
  },
  itemName: {
    fontSize: 15,
    fontWeight: '700',
    color: COLORS.text,
  },
  itemNameSelected: {
    color: '#2e4d38',
  },
  itemEmail: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginTop: 2,
    fontWeight: '500',
  },
  selectedCheck: {
    fontSize: 16,
    fontWeight: '900',
    color: '#2e4d38',
    marginLeft: 12,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  statusText: {
    marginTop: 12,
    fontSize: 14,
    color: COLORS.textMuted,
    fontWeight: '600',
  },
  errorIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  errorText: {
    fontSize: 14,
    color: COLORS.danger,
    textAlign: 'center',
    marginBottom: 16,
    fontWeight: '600',
  },
  retryBtn: {
    backgroundColor: COLORS.primary,
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
  },
  retryText: {
    color: COLORS.white,
    fontSize: 14,
    fontWeight: '700',
  },
  emptyIcon: {
    fontSize: 36,
    marginBottom: 8,
  },
  emptyText: {
    fontSize: 14,
    color: COLORS.textMuted,
    fontWeight: '600',
  },
});
