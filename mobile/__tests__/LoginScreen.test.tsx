/**
 * Phase 24A-3: LoginScreen Baseline Tests (RNTL v14)
 *
 * Tests existing sign-in and forgot-password behavior
 * without calling Cognito or changing component behavior.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';

// Mock auth context
const mockLogin = jest.fn();
jest.mock('../src/auth/useAuth', () => ({
  useAuth: () => ({
    login: mockLogin,
    logout: jest.fn(),
    user: null,
    role: null,
    isAuthenticated: false,
    isLoading: false,
  }),
}));

// Mock cognito functions
const mockForgotPassword = jest.fn().mockResolvedValue(undefined);
const mockConfirmForgotPassword = jest.fn().mockResolvedValue(undefined);
jest.mock('../src/auth/cognito', () => ({
  forgotPassword: (...args: any[]) => mockForgotPassword(...args),
  confirmForgotPassword: (...args: any[]) => mockConfirmForgotPassword(...args),
}));

import { LoginScreen } from '../src/screens/LoginScreen';

beforeEach(() => {
  jest.clearAllMocks();
});

describe('LoginScreen - Sign In', () => {
  it('renders email and password inputs', async () => {
    await render(<LoginScreen />);
    expect(screen.getByPlaceholderText('email@example.com')).toBeTruthy();
    expect(screen.getByPlaceholderText('Enter password')).toBeTruthy();
  });

  it('renders Log In button', async () => {
    await render(<LoginScreen />);
    expect(screen.getByText('Log In')).toBeTruthy();
  });

  it('renders Forgot password link', async () => {
    await render(<LoginScreen />);
    expect(screen.getByText('Forgot password?')).toBeTruthy();
  });

  it('shows validation error for empty fields', async () => {
    await render(<LoginScreen />);
    await fireEvent.press(screen.getByText('Log In'));
    await waitFor(() => {
      expect(screen.getByText('Please enter your email and password.')).toBeTruthy();
    });
  });
});

describe('LoginScreen - Forgot Password Flow', () => {
  it('transitions to forgot-password mode', async () => {
    await render(<LoginScreen />);
    await fireEvent.press(screen.getByText('Forgot password?'));
    expect(screen.getByText('Forgot Password')).toBeTruthy();
    expect(screen.getByText('Send Reset Code')).toBeTruthy();
  });

  it('sends reset code on valid email', async () => {
    await render(<LoginScreen />);
    await fireEvent.press(screen.getByText('Forgot password?'));
    await fireEvent.changeText(
      screen.getByPlaceholderText('email@example.com'),
      'test@example.com'
    );
    await fireEvent.press(screen.getByText('Send Reset Code'));
    await waitFor(() => {
      expect(mockForgotPassword).toHaveBeenCalledWith('test@example.com');
    });
  });

  it('transitions to reset-code entry after sending', async () => {
    await render(<LoginScreen />);
    await fireEvent.press(screen.getByText('Forgot password?'));
    await fireEvent.changeText(
      screen.getByPlaceholderText('email@example.com'),
      'test@example.com'
    );
    await fireEvent.press(screen.getByText('Send Reset Code'));
    await waitFor(() => {
      expect(screen.getByText('Enter Reset Code')).toBeTruthy();
      expect(screen.getByPlaceholderText('6-digit code')).toBeTruthy();
    });
  });

  it('shows error for empty email in forgot-password mode', async () => {
    await render(<LoginScreen />);
    await fireEvent.press(screen.getByText('Forgot password?'));
    await fireEvent.press(screen.getByText('Send Reset Code'));
    await waitFor(() => {
      expect(screen.getByText('Please enter your email address.')).toBeTruthy();
    });
  });
});
