/**
 * Phase 24A-3: Jest Setup for Mobile Test Foundation
 *
 * Provides minimal deterministic mocks for platform dependencies.
 * No global console suppression — tests must not produce avoidable warnings.
 */

// OPS-3A.4A: The app config resolver (src/api/config.ts) now fails closed when
// EXPO_PUBLIC_APP_ENV is not explicitly set. Tests transitively import that
// module via the API/auth layers and historically asserted the production
// identifiers, so declare the production environment explicitly for the test
// runtime. Config-selection edge cases (missing/invalid env, dev fail-closed)
// are covered directly against the pure resolveConfig() in config.test.ts.
process.env.EXPO_PUBLIC_APP_ENV = 'production';

// Mock expo-secure-store
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn().mockResolvedValue(null),
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));

// Mock @react-navigation/native
jest.mock('@react-navigation/native', () => {
  const React = require('react');
  return {
    useNavigation: () => ({
      navigate: jest.fn(),
      goBack: jest.fn(),
      setOptions: jest.fn(),
    }),
    useRoute: () => ({
      params: {},
    }),
    useFocusEffect: (cb) => {
      React.useEffect(() => { cb(); }, []);
    },
    NavigationContainer: ({ children }) => children,
  };
});

// Mock @react-navigation/bottom-tabs
jest.mock('@react-navigation/bottom-tabs', () => ({
  createBottomTabNavigator: () => ({
    Navigator: ({ children }) => children,
    Screen: ({ children }) => children,
  }),
}));

// Mock @react-navigation/native-stack
jest.mock('@react-navigation/native-stack', () => ({
  createNativeStackNavigator: () => ({
    Navigator: ({ children }) => children,
    Screen: ({ children }) => children,
  }),
}));

// Mock react-native-safe-area-context
jest.mock('react-native-safe-area-context', () => ({
  SafeAreaProvider: ({ children }) => children,
  SafeAreaView: ({ children }) => children,
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
