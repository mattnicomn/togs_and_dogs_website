import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import AdminDashboard from '../src/components/AdminDashboard';
import { getSession, getEffectiveRole } from '../src/api/auth';
import { 
  getAdminRequests, 
  getStaff, 
  getClients, 
  getGoogleStatus, 
  getTenantInfo,
  initiateGoogleAuth
} from '../src/api/client';

// Mock all required client & auth APIs
vi.mock('../src/api/auth', () => ({
  signIn: vi.fn(),
  getSession: vi.fn(),
  getEffectiveRole: vi.fn(),
}));

vi.mock('../src/api/client', () => ({
  getAdminRequests: vi.fn(),
  reviewRequest: vi.fn(),
  assignWorker: vi.fn(),
  getGoogleStatus: vi.fn(),
  initiateGoogleAuth: vi.fn(),
  getPet: vi.fn(),
  updatePet: vi.fn(),
  createPet: vi.fn(),
  processCancellationDecision: vi.fn(),
  performAdminAction: vi.fn(),
  purgeRecord: vi.fn(),
  purgeRecordsBulk: vi.fn(),
  getStaff: vi.fn(),
  createStaff: vi.fn(),
  updateStaff: vi.fn(),
  disableStaff: vi.fn(),
  onboardStaff: vi.fn(),
  linkCognitoUser: vi.fn(),
  resendInvite: vi.fn(),
  resetStaffPassword: vi.fn(),
  setStaffTempPassword: vi.fn(),
  getClients: vi.fn(),
  createClient: vi.fn(),
  updateClient: vi.fn(),
  disableClient: vi.fn(),
  onboardClient: vi.fn(),
  resendClientInvite: vi.fn(),
  resetClientPassword: vi.fn(),
  setClientTempPassword: vi.fn(),
  linkClientCognitoUser: vi.fn(),
  getExportData: vi.fn(),
  createAdminBooking: vi.fn(),
  listAdminClientPets: vi.fn(),
  getTenantInfo: vi.fn(),
}));

describe('Google Calendar Integration RBAC Frontend Tests', () => {
  const mockSession = {
    getIdToken: () => ({
      payload: {
        email: 'user@example.com',
        sub: 'user-sub-123',
        name: 'Test User'
      }
    })
  };

  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(mockSession);
    getAdminRequests.mockResolvedValue({ requests: [] });
    getStaff.mockResolvedValue({ staff: [] });
    getClients.mockResolvedValue({ clients: [] });
    getTenantInfo.mockResolvedValue({
      company_name: 'Togs and Dogs',
      calendar_provider: 'google',
      calendar_enabled: true
    });
  });

  it('1. staff role sees calendar status and degraded health message but NOT connect button', async () => {
    getEffectiveRole.mockReturnValue('staff');
    getGoogleStatus.mockResolvedValue({ status: 'VALIDATION_FAILED' });

    render(<AdminDashboard />);

    // Wait for authentication & data load to complete
    await waitFor(() => {
      expect(screen.getByText(/Google Calendar connection needs reconnect/i)).toBeInTheDocument();
    });

    // Staff should see the degraded message banner
    expect(screen.getByText(/Google Calendar connection needs reconnect/i)).toBeInTheDocument();
    expect(screen.getByText(/⚠️/)).toBeInTheDocument();

    // Staff should NOT see the Reconnect/Connect buttons
    expect(screen.queryByRole('button', { name: /Reconnect Calendar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Connect Calendar/i })).not.toBeInTheDocument();
  });

  it('2. staff role does NOT see Connect button in System Integrations card', async () => {
    getEffectiveRole.mockReturnValue('staff');
    getGoogleStatus.mockResolvedValue({ status: 'NOT_CONNECTED' });

    render(<AdminDashboard />);

    // Go to Settings tab/section where the integration card is rendered
    await waitFor(() => {
      expect(screen.getByText(/Google Calendar is not connected/i)).toBeInTheDocument();
    });

    // Integration details should be visible (read-only)
    expect(screen.getAllByText(/Google Calendar/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Connected Account/i)).toBeInTheDocument();

    // But the action button must not be visible
    expect(screen.queryByRole('button', { name: /Connect Calendar/i })).not.toBeInTheDocument();
  });

  it('3. owner role sees Reconnect button in health banner and Connect button in card', async () => {
    getEffectiveRole.mockReturnValue('owner');
    getGoogleStatus.mockResolvedValue({ status: 'VALIDATION_FAILED' });

    render(<AdminDashboard />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Reconnect Calendar/i })).toBeInTheDocument();
    });

    // Connect / Reconnect action should be allowed and clickable
    const button = screen.getByRole('button', { name: /Reconnect Calendar/i });
    expect(button).toBeInTheDocument();

    initiateGoogleAuth.mockResolvedValue({ auth_url: 'https://mock-google-auth-url' });
    fireEvent.click(button);
    expect(initiateGoogleAuth).toHaveBeenCalled();
  });

  it('4. admin role sees Connect button when NOT_CONNECTED', async () => {
    getEffectiveRole.mockReturnValue('admin');
    getGoogleStatus.mockResolvedValue({ status: 'NOT_CONNECTED' });

    render(<AdminDashboard />);

    await waitFor(() => {
      // Connect button is in both health banner and integration card
      const buttons = screen.getAllByRole('button', { name: /Connect Calendar/i });
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it('5. Scheduler remains fully accessible to staff', async () => {
    getEffectiveRole.mockReturnValue('staff');
    getGoogleStatus.mockResolvedValue({ status: 'CONNECTED' });

    render(<AdminDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/Master Scheduler/i)).toBeInTheDocument();
    });
    
    // Scheduler view is active and responsive
    expect(screen.getByText(/Timeframe/i)).toBeInTheDocument();
  });
});
