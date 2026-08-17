import React from 'react';
import { StyleSheet, View, ActivityIndicator } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useAuth } from '../auth/useAuth';
import { AuthNavigator } from './AuthNavigator';
import { DashboardScreen } from '../screens/DashboardScreen';
import { MyPetsScreen } from '../screens/MyPetsScreen';
import { RequestListScreen } from '../screens/RequestListScreen';
import { ScheduleScreen } from '../screens/ScheduleScreen';
import { BookingsScreen } from '../screens/BookingsScreen';
import { RequestDetailScreen } from '../screens/RequestDetailScreen';
import { IntakeScreen } from '../screens/IntakeScreen';
import { COLORS } from '../theme/colors';
import { AdminTabParamList } from './types';

const AdminTab = createBottomTabNavigator<AdminTabParamList>();
const Tab = createBottomTabNavigator();

// Admin / Owner Tab Navigator
const AdminTabs = () => {
  return (
    <AdminTab.Navigator
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
      <AdminTab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{
          tabBarLabel: 'Dashboard',
          tabBarIcon: ({ color }) => (
            <ActivityIndicator color={color} size="small" animating={false} />
          ),
        }}
      />
      <AdminTab.Screen
        name="Requests"
        component={RequestListScreen}
        options={{
          tabBarLabel: 'Requests',
          tabBarIcon: ({ color }) => (
            <ActivityIndicator color={color} size="small" animating={false} />
          ),
        }}
      />
      <AdminTab.Screen
        name="Schedule"
        component={ScheduleScreen}
        options={{
          tabBarLabel: 'Schedule',
          tabBarIcon: ({ color }) => (
            <ActivityIndicator color={color} size="small" animating={false} />
          ),
        }}
      />
    </AdminTab.Navigator>
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
      <Tab.Screen
        name="MyPets"
        component={MyPetsScreen}
        options={{
          tabBarLabel: 'My Pets',
          tabBarIcon: ({ color }) => (
            <ActivityIndicator color={color} size="small" animating={false} />
          ),
        }}
      />
    </Tab.Navigator>
  );
};

const AdminStack = createNativeStackNavigator();
const AdminNavigator = () => (
  <AdminStack.Navigator screenOptions={{ headerShown: false }}>
    <AdminStack.Screen name="AdminTabs" component={AdminTabs} />
    <AdminStack.Screen 
      name="RequestDetail" 
      component={RequestDetailScreen} 
      options={{ 
        headerShown: true, 
        title: 'Booking Details',
        headerStyle: { backgroundColor: COLORS.cardBg },
        headerTintColor: COLORS.text,
        headerTitleStyle: { fontWeight: '800', fontSize: 16 }
      }} 
    />
  </AdminStack.Navigator>
);

const StaffStack = createNativeStackNavigator();
const StaffNavigator = () => (
  <StaffStack.Navigator screenOptions={{ headerShown: false }}>
    <StaffStack.Screen name="StaffTabs" component={StaffTabs} />
    <StaffStack.Screen 
      name="RequestDetail" 
      component={RequestDetailScreen} 
      options={{ 
        headerShown: true, 
        title: 'Booking Details',
        headerStyle: { backgroundColor: COLORS.cardBg },
        headerTintColor: COLORS.text,
        headerTitleStyle: { fontWeight: '800', fontSize: 16 }
      }} 
    />
  </StaffStack.Navigator>
);

const ClientStack = createNativeStackNavigator();
const ClientNavigator = () => (
  <ClientStack.Navigator screenOptions={{ headerShown: false }}>
    <ClientStack.Screen name="ClientTabs" component={ClientTabs} />
    <ClientStack.Screen
      name="IntakeScreen"
      component={IntakeScreen}
      options={{ headerShown: false }}
    />
  </ClientStack.Navigator>
);

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
      return <AdminNavigator />;
    case 'staff':
      return <StaffNavigator />;
    default:
      return <ClientNavigator />;
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
