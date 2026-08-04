import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminDashboard from '../src/components/AdminDashboard';
import { getEffectiveRole, getSession } from '../src/api/auth';
import {
  getAdminRequests,
  getClients,
  getGoogleStatus,
  getStaff,
  getTenantInfo,
  resendInvite,
  resetStaffPassword,
  setStaffTempPassword
} from '../src/api/client';

window.HTMLElement.prototype.scrollIntoView = vi.fn();

vi.mock('../src/api/auth', () => ({
  signIn: vi.fn(),
  getSession: vi.fn(),
  getEffectiveRole: vi.fn()
}));

vi.mock('../src/api/client', () => ({
  getAdminRequests: vi.fn(),
  getClients: vi.fn(),
  getStaff: vi.fn(),
  getTenantInfo: vi.fn(),
  getGoogleStatus: vi.fn(),
  resendInvite: vi.fn(),
  resetStaffPassword: vi.fn(),
  setStaffTempPassword: vi.fn()
}));

const mockSession = {
  getIdToken: () => ({
    payload: {
      email: 'owner@example.com',
      sub: 'owner-sub-123',
      name: 'Owner User'
    }
  })
};

const confirmedStaff = {
  staff_id: 'staff-target',
  display_name: 'Target Staff',
  email: 'target@example.com',
  role: 'Staff',
  cognito_sub: 'target-sub-123',
  cognito_username: 'target@example.com',
  cognito_status: 'CONFIRMED',
  identity_state: 'linked_active',
  is_active: true,
  is_assignable: true,
  is_protected: false,
  is_orphaned_identity: false
};

const initialLoginExplanation = 'This user has not completed their initial login. Use Resend Invite or Set Temporary Password instead.';

const openStaffDrawer = async (staffOverrides = {}) => {
  const staff = { ...confirmedStaff, ...staffOverrides };
  getStaff.mockResolvedValue({ staff: [staff] });

  render(<AdminDashboard />);
  fireEvent.click(await screen.findByRole('button', { name: 'Staff Management' }));
  await screen.findByText('Staff & Profile Management');
  fireEvent.click(await screen.findByRole('button', { name: /Staff profile for Target Staff/i }));

  return {
    staff,
    resetButton: screen.getByRole('button', { name: 'Send Password Reset Email' })
  };
};

describe('AdminDashboard staff password-reset state awareness', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(mockSession);
    getEffectiveRole.mockReturnValue('owner');
    getAdminRequests.mockResolvedValue({ requests: [] });
    getClients.mockResolvedValue({ clients: [] });
    getGoogleStatus.mockResolvedValue({});
    getTenantInfo.mockResolvedValue({
      company_name: 'Togs and Dogs',
      support_email: 'support@example.com'
    });
    resendInvite.mockResolvedValue({});
    resetStaffPassword.mockResolvedValue({});
    setStaffTempPassword.mockResolvedValue({});
  });

  it('disables normal reset for FORCE_CHANGE_PASSWORD and does not dispatch it', async () => {
    const { resetButton } = await openStaffDrawer({
      cognito_status: 'FORCE_CHANGE_PASSWORD',
      identity_state: 'linked_invited'
    });

    expect(resetButton).toBeDisabled();
    expect(resetButton).toHaveAttribute('title', initialLoginExplanation);

    fireEvent.click(resetButton);

    expect(screen.queryByRole('heading', { name: /Send a password reset email/i })).not.toBeInTheDocument();
    expect(resetStaffPassword).not.toHaveBeenCalled();
  });

  it('disables normal reset for the existing linked_invited identity state', async () => {
    const { resetButton } = await openStaffDrawer({
      cognito_status: 'RESET_REQUIRED',
      identity_state: 'linked_invited'
    });

    expect(resetButton).toBeDisabled();
    expect(resetButton).toHaveAttribute(
      'title',
      'This user has not completed their initial login. Use Set Temporary Password instead.'
    );
    expect(screen.getByRole('button', { name: 'Resend Invite' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Set Temporary Password' })).toBeEnabled();
  });

  it('preserves confirmed-user reset confirmation and dispatch behavior', async () => {
    const { staff, resetButton } = await openStaffDrawer();

    expect(resetButton).toBeEnabled();
    expect(resetButton).not.toHaveAttribute('title');

    fireEvent.click(resetButton);
    expect(screen.getByRole('heading', { name: `Send a password reset email to ${staff.display_name}?` })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    await waitFor(() => {
      expect(resetStaffPassword).toHaveBeenCalledWith(staff.staff_id);
    });
  });

  it('preserves protected explanation precedence over self, orphaned, and invitation state', async () => {
    const { resetButton } = await openStaffDrawer({
      email: 'owner@example.com',
      cognito_sub: 'owner-sub-123',
      cognito_status: 'FORCE_CHANGE_PASSWORD',
      identity_state: 'linked_invited',
      is_protected: true,
      is_orphaned_identity: true
    });

    expect(resetButton).toBeDisabled();
    expect(resetButton).toHaveAttribute('title', 'This account is protected and cannot be modified');
  });

  it('preserves self explanation precedence over orphaned and invitation state', async () => {
    const { resetButton } = await openStaffDrawer({
      email: 'owner@example.com',
      cognito_sub: 'owner-sub-123',
      cognito_status: 'FORCE_CHANGE_PASSWORD',
      identity_state: 'linked_invited',
      is_orphaned_identity: true
    });

    expect(resetButton).toBeDisabled();
    expect(resetButton).toHaveAttribute('title', 'You cannot modify your own account security settings');
  });

  it('preserves orphaned explanation precedence over invitation state', async () => {
    const { resetButton } = await openStaffDrawer({
      cognito_status: 'FORCE_CHANGE_PASSWORD',
      identity_state: 'linked_invited',
      is_orphaned_identity: true
    });

    expect(resetButton).toBeDisabled();
    expect(resetButton).toHaveAttribute('title', 'This login is orphaned');
  });

  it('leaves Resend Invite and Set Temporary Password behavior unchanged', async () => {
    const { staff } = await openStaffDrawer({
      cognito_status: 'FORCE_CHANGE_PASSWORD',
      identity_state: 'linked_invited'
    });

    const resendButton = screen.getByRole('button', { name: 'Resend Invite' });
    const temporaryPasswordButton = screen.getByRole('button', { name: 'Set Temporary Password' });
    expect(resendButton).toBeEnabled();
    expect(temporaryPasswordButton).toBeEnabled();

    fireEvent.click(resendButton);
    await waitFor(() => {
      expect(resendInvite).toHaveBeenCalledWith(staff.staff_id);
    });

    fireEvent.click(temporaryPasswordButton);
    fireEvent.change(screen.getByPlaceholderText('Enter temporary password'), {
      target: { value: 'TemporaryPass123!' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Set Password' }));

    await waitFor(() => {
      expect(setStaffTempPassword).toHaveBeenCalledWith(staff.staff_id, 'TemporaryPass123!');
    });
  });
});
