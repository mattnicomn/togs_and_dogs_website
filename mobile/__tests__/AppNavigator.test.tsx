import React from 'react';
import { render } from '@testing-library/react-native';

jest.mock('@react-navigation/bottom-tabs', () => ({
  createBottomTabNavigator: () => {
    const React = require('react');
    const { Text } = require('react-native');
    return {
      Navigator: ({ children }: { children: React.ReactNode }) => children,
      Screen: ({ name }: { name: string }) => React.createElement(Text, null, name),
    };
  },
}));

jest.mock('@react-navigation/native-stack', () => {
  const React = require('react');
  return {
    createNativeStackNavigator: () => ({
      Navigator: ({ children }: { children: React.ReactNode }) => children,
      Screen: ({ name, component: Component }: { name: string; component: React.ComponentType }) =>
        name === 'AdminTabs' ? React.createElement(Component) : null,
    }),
  };
});

jest.mock('../src/auth/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    role: 'owner',
  }),
}));

jest.mock('../src/screens/DashboardScreen', () => ({ DashboardScreen: () => null }));
jest.mock('../src/screens/RequestListScreen', () => ({ RequestListScreen: () => null }));
jest.mock('../src/screens/ScheduleScreen', () => ({ ScheduleScreen: () => null }));
jest.mock('../src/screens/RequestDetailScreen', () => ({ RequestDetailScreen: () => null }));

import { AppNavigator } from '../src/navigation/AppNavigator';

describe('AppNavigator admin tabs', () => {
  it('preserves the ordinary Dashboard, Requests, and Schedule tab routes', async () => {
    const view = await render(<AppNavigator />);

    expect(view.getByText('Dashboard')).toBeTruthy();
    expect(view.getByText('Requests')).toBeTruthy();
    expect(view.getByText('Schedule')).toBeTruthy();
  });
});
