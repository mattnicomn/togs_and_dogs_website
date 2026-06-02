import React from 'react';
import { StyleSheet, View, ActivityIndicator } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useAuth } from '../auth/useAuth';
import { AuthNavigator } from './AuthNavigator';
import { DashboardScreen } from '../screens/DashboardScreen';
import { RequestListScreen } from '../screens/RequestListScreen';
import { ScheduleScreen } from '../screens/ScheduleScreen';
import { BookingsScreen } from '../screens/BookingsScreen';
import { COLORS } from '../theme/colors';

const Tab = createBottomTabNavigator();

// Admin / Owner Tab Navigator
const AdminTabs = () => {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: COLORS.primary,
        tabBarInactiveTintColor: COLORS.textMuted,
        tabBarStyle: {
          backgroundColor: COLORS.cardBg,
          borderTopColor: COLORS.border,
          height: 60,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: 12,
          fontWeight: '700',
        },
      }}
    >
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{
          tabBarLabel: 'Dashboard',
          tabBarIcon: ({ color }) => (
            <ActivityIndicator color={color} size="small" animating={false} />
          ),
        }}
      />
      <Tab.Screen
        name="Requests"
        component={RequestListScreen}
        options={{
          tabBarLabel: 'Requests',
          tabBarIcon: ({ color }) => (
            <ActivityIndicator color={color} size="small" animating={false} />
          ),
        }}
      />
    </Tab.Navigator>
  );
};

// Staff Tab Navigator
const StaffTabs = () => {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: COLORS.primary,
        tabBarInactiveTintColor: COLORS.textMuted,
        tabBarStyle: {
          backgroundColor: COLORS.cardBg,
          borderTopColor: COLORS.border,
          height: 60,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: 12,
          fontWeight: '700',
        },
      }}
    >
      <Tab.Screen
        name="Schedule"
        component={ScheduleScreen}
        options={{
          tabBarLabel: 'Schedule',
          tabBarIcon: ({ color }) => (
            <ActivityIndicator color={color} size="small" animating={false} />
          ),
        }}
      />
    </Tab.Navigator>
  );
};

// Client Tab Navigator
const ClientTabs = () => {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: COLORS.primary,
        tabBarInactiveTintColor: COLORS.textMuted,
        tabBarStyle: {
          backgroundColor: COLORS.cardBg,
          borderTopColor: COLORS.border,
          height: 60,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: 12,
          fontWeight: '700',
        },
      }}
    >
      <Tab.Screen
        name="Bookings"
        component={BookingsScreen}
        options={{
          tabBarLabel: 'Bookings',
          tabBarIcon: ({ color }) => (
            <ActivityIndicator color={color} size="small" animating={false} />
          ),
        }}
      />
    </Tab.Navigator>
  );
};

export const AppNavigator = () => {
  const { isAuthenticated, role, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
      </View>
    );
  }

  if (!isAuthenticated) {
    return <AuthNavigator />;
  }

  switch (role) {
    case 'owner':
    case 'admin':
      return <AdminTabs />;
    case 'staff':
      return <StaffTabs />;
    default:
      return <ClientTabs />;
  }
};

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: COLORS.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
