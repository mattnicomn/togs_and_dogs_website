import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminDashboard from '../src/components/AdminDashboard';
import {
  confirmForgotPassword,
  forgotPassword,
  getEffectiveRole,
  getSession,
  signIn
} from '../src/api/auth';

vi.mock('../src/api/auth', () => ({
  signIn: vi.fn(),
  forgotPassword: vi.fn(),
  confirmForgotPassword: vi.fn(),
  getSession: vi.fn(),
  getEffectiveRole: vi.fn()
}));

const renderLogin = async () => {
  render(<AdminDashboard />);
  await screen.findByRole('heading', { name: 'Staff Portal' });
};

const openRecovery = async (email = '') => {
  await renderLogin();
  if (email) {
    fireEvent.change(screen.getByLabelText('Email Address'), { target: { value: email } });
  }
  fireEvent.click(screen.getByRole('button', { name: 'Forgot password?' }));
  await screen.findByRole('heading', { name: 'Forgot Password' });
};

const reachConfirmation = async () => {
  await openRecovery('  Customer@Example.COM  ');
  fireEvent.click(screen.getByRole('button', { name: 'Send Reset Code' }));
  await screen.findByRole('heading', { name: 'Enter Reset Code' });
};

describe('AdminDashboard customer self-service password recovery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(null);
    forgotPassword.mockResolvedValue(undefined);
    confirmForgotPassword.mockResolvedValue(undefined);
  });

  it('renders a keyboard-accessible Forgot password action and enters recovery', async () => {
    await renderLogin();

    const action = screen.getByRole('button', { name: 'Forgot password?' });
    expect(action).toBeEnabled();
    fireEvent.click(action);

    expect(await screen.findByRole('heading', { name: 'Forgot Password' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email Address')).toBeInTheDocument();
  });

  it('validates a missing recovery email without calling Cognito', async () => {
    await openRecovery();
    fireEvent.click(screen.getByRole('button', { name: 'Send Reset Code' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Please enter your email address.');
    expect(forgotPassword).not.toHaveBeenCalled();
  });

  it('normalizes the email and transitions after a successful code request', async () => {
    await reachConfirmation();

    expect(forgotPassword).toHaveBeenCalledTimes(1);
    expect(forgotPassword).toHaveBeenCalledWith('customer@example.com');
    expect(screen.getByLabelText('Verification Code')).toBeInTheDocument();
  });

  it('prevents duplicate code requests while submission is pending', async () => {
    let resolveRequest;
    forgotPassword.mockImplementation(() => new Promise((resolve) => {
      resolveRequest = resolve;
    }));
    await openRecovery('customer@example.com');

    const sendButton = screen.getByRole('button', { name: 'Send Reset Code' });
    fireEvent.click(sendButton);

    expect(await screen.findByRole('button', { name: 'Sending...' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Sending...' }));
    expect(forgotPassword).toHaveBeenCalledTimes(1);

    resolveRequest();
    expect(await screen.findByRole('heading', { name: 'Enter Reset Code' })).toBeInTheDocument();
  });

  it('shows a safe generic code-request error without exposing SDK details', async () => {
    forgotPassword.mockRejectedValue(new Error('UserNotFoundException: secret detail'));
    await openRecovery('missing@example.com');
    fireEvent.click(screen.getByRole('button', { name: 'Send Reset Code' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to send a reset code right now. Please try again.');
    expect(screen.queryByText(/UserNotFoundException|secret detail/i)).not.toBeInTheDocument();
  });

  it('validates a missing verification code', async () => {
    await reachConfirmation();
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Please enter your verification code.');
    expect(confirmForgotPassword).not.toHaveBeenCalled();
  });

  it('validates missing, short, and mismatched passwords', async () => {
    await reachConfirmation();
    fireEvent.change(screen.getByLabelText('Verification Code'), { target: { value: '123456' } });

    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Please enter a new password.');

    fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'short' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Please confirm your new password.');

    fireEvent.change(screen.getByLabelText('Confirm New Password'), { target: { value: 'short' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Password must be at least 8 characters.');

    fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'Password123!' } });
    fireEvent.change(screen.getByLabelText('Confirm New Password'), { target: { value: 'Password456!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Passwords do not match.');
    expect(confirmForgotPassword).not.toHaveBeenCalled();
  });

  it('confirms with normalized inputs and shows a distinct success state', async () => {
    await reachConfirmation();
    fireEvent.change(screen.getByLabelText('Verification Code'), { target: { value: ' 123456 ' } });
    fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'Password123!' } });
    fireEvent.change(screen.getByLabelText('Confirm New Password'), { target: { value: 'Password123!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

    await waitFor(() => {
      expect(confirmForgotPassword).toHaveBeenCalledWith('customer@example.com', '123456', 'Password123!');
    });
    expect(await screen.findByRole('status')).toHaveTextContent('Password reset successfully.');
    expect(screen.getByRole('button', { name: 'Back to Sign In' })).toBeInTheDocument();
  });

  it('shows a safe confirmation error without exposing SDK details', async () => {
    confirmForgotPassword.mockRejectedValue({
      code: 'CodeMismatchException',
      message: 'CodeMismatchException: secret detail'
    });
    await reachConfirmation();
    fireEvent.change(screen.getByLabelText('Verification Code'), { target: { value: '999999' } });
    fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'Password123!' } });
    fireEvent.change(screen.getByLabelText('Confirm New Password'), { target: { value: 'Password123!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid verification code. Please check the code and try again.');
    expect(screen.queryByText(/CodeMismatchException|secret detail/i)).not.toBeInTheDocument();
  });

  it('returns from confirmation to request a new code while preserving the email', async () => {
    await reachConfirmation();
    fireEvent.click(screen.getByRole('button', { name: 'Request a New Code' }));

    expect(await screen.findByRole('heading', { name: 'Forgot Password' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email Address')).toHaveValue('customer@example.com');
    expect(forgotPassword).toHaveBeenCalledTimes(1);
  });

  it('returns to sign in with the normalized email and no password', async () => {
    await reachConfirmation();
    fireEvent.change(screen.getByLabelText('Verification Code'), { target: { value: '123456' } });
    fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'Password123!' } });
    fireEvent.change(screen.getByLabelText('Confirm New Password'), { target: { value: 'Password123!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));
    await screen.findByRole('status');
    fireEvent.click(await screen.findByRole('button', { name: 'Back to Sign In' }));

    expect(await screen.findByRole('heading', { name: 'Staff Portal' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email Address')).toHaveValue('customer@example.com');
    expect(screen.getByLabelText('Password')).toHaveValue('');
  });

  it('preserves the existing normal login call', async () => {
    signIn.mockRejectedValue(new Error('Synthetic login failure'));
    await renderLogin();
    fireEvent.change(screen.getByLabelText('Email Address'), { target: { value: 'owner@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'SyntheticPassword1!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));

    await waitFor(() => {
      expect(signIn).toHaveBeenCalledWith('owner@example.com', 'SyntheticPassword1!');
    });
    expect(await screen.findByText('Synthetic login failure')).toBeInTheDocument();
  });

  it('preserves the existing required-new-password challenge branch', async () => {
    const cognitoUser = { completeNewPasswordChallenge: vi.fn() };
    signIn.mockResolvedValue({
      challenge: 'NEW_PASSWORD_REQUIRED',
      userAttributes: { email: 'invited@example.com' },
      cognitoUser
    });
    await renderLogin();
    fireEvent.change(screen.getByLabelText('Email Address'), { target: { value: 'invited@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'TemporaryPassword1!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));

    expect(await screen.findByRole('heading', { name: 'Create New Password' })).toBeInTheDocument();
    expect(cognitoUser.completeNewPasswordChallenge).not.toHaveBeenCalled();
    expect(getEffectiveRole).not.toHaveBeenCalled();
  });
});
