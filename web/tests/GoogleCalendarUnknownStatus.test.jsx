import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import AdminDashboard from '../src/components/AdminDashboard';
import * as client from '../src/api/client';
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

vi.mock('../src/components/UserProfile', () => ({ default: () => null }));

const session = { getIdToken: () => ({ payload: { email: 'synthetic@example.test', sub: 'synthetic' } }) };
const unknownMessage = /Google Calendar status is not current/;
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal('fetch', vi.fn(() => { throw new Error('Live requests forbidden'); }));
  getSession.mockResolvedValue(session);
  getEffectiveRole.mockReturnValue('admin');
  getAdminRequests.mockResolvedValue({ requests: [] });
  getStaff.mockResolvedValue({ staff: [] });
  getClients.mockResolvedValue({ clients: [] });
  getTenantInfo.mockResolvedValue({ calendar_provider: 'google', calendar_enabled: true });
});
afterEach(() => vi.unstubAllGlobals());

it('renders UNKNOWN explicitly without claiming connected, disconnected, or revoked', async () => {
  getGoogleStatus.mockResolvedValue({ status: 'UNKNOWN' });
  const { container } = render(<AdminDashboard />);
  expect(await screen.findByText(unknownMessage)).toBeInTheDocument();
  const badge = container.querySelector('.integration-status-badge');
  expect(badge).toHaveTextContent('Status not current');
  expect(badge).toHaveClass('status-unknown');
  expect(badge).not.toHaveClass('status-connected', 'status-disconnected', 'status-reconnect');
  expect(screen.getByText('Not confirmed')).toBeInTheDocument();
  expect(screen.queryByText('Business Account')).not.toBeInTheDocument();
  expect(screen.queryByText(/Google Calendar is not connected/)).not.toBeInTheDocument();
  expect(screen.queryByText(/connection needs reconnect/)).not.toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: 'Connect Calendar' }).length).toBeGreaterThan(0);
  expect(screen.queryByRole('button', { name: /disconnect/i })).not.toBeInTheDocument();
  await act(async () => {});
  expect(getGoogleStatus).toHaveBeenCalledTimes(1);
  expect(initiateGoogleAuth).not.toHaveBeenCalled();
  expect(fetch).not.toHaveBeenCalled();
  for (const [name, api] of Object.entries(client)) {
    if (!/^(get|list)/.test(name)) expect(api).not.toHaveBeenCalled();
  }
});

it.each([
  ['CONNECTED', 'Connected', 'status-connected'],
  ['NOT_CONNECTED', 'Not Connected', 'status-disconnected'],
  ['VALIDATION_FAILED', 'Needs Reconnect', 'status-reconnect'],
  ['CREDENTIALS_MISSING', 'Error', 'status-error'],
])('preserves %s rendering', async (status, label, className) => {
  getGoogleStatus.mockResolvedValue({ status });
  const { container } = render(<AdminDashboard />);
  await waitFor(() => expect(container.querySelector('.integration-status-badge')).toHaveTextContent(label));
  expect(container.querySelector('.integration-status-badge')).toHaveClass(className);
  expect(screen.queryByText(unknownMessage)).not.toBeInTheDocument();
  if (status === 'CONNECTED') expect(screen.getByText('Business Account')).toBeInTheDocument();
  if (status === 'NOT_CONNECTED') expect(screen.getByText(/Google Calendar is not connected/)).toBeInTheDocument();
  if (status === 'VALIDATION_FAILED') expect(screen.getByText(/connection needs reconnect/)).toBeInTheDocument();
  if (status === 'CREDENTIALS_MISSING') expect(screen.getByText(/Please contact support/)).toBeInTheDocument();
  expect(initiateGoogleAuth).not.toHaveBeenCalled();
});

it.each(['unknown', 'unavailable'])('replaces prior CONNECTED after %s', async (outcome) => {
  // StrictMode provides two existing bootstrap invocations, without adding a refresh control.
  const secondSession = deferred();
  getSession.mockResolvedValueOnce(session).mockReturnValueOnce(secondSession.promise);
  getGoogleStatus.mockResolvedValueOnce({ status: 'CONNECTED' });
  if (outcome === 'unknown') getGoogleStatus.mockResolvedValueOnce({ status: 'UNKNOWN' });
  else getGoogleStatus.mockRejectedValueOnce(new Error('503 unavailable'));
  const { container } = render(<React.StrictMode><AdminDashboard /></React.StrictMode>);
  await waitFor(() => expect(container.querySelector('.integration-status-badge')).toHaveTextContent('Connected'));
  await act(async () => { secondSession.resolve(session); });
  expect(await screen.findByText(unknownMessage)).toBeInTheDocument();
  expect(container.querySelector('.integration-status-badge')).toHaveTextContent('Status not current');
  expect(screen.queryByText('Business Account')).not.toBeInTheDocument();
  expect(getGoogleStatus).toHaveBeenCalledTimes(2);
  expect(initiateGoogleAuth).not.toHaveBeenCalled();
});

it('ignores an older CONNECTED response after a newer UNKNOWN response', async () => {
  const older = deferred();
  getGoogleStatus.mockReturnValueOnce(older.promise).mockResolvedValueOnce({ status: 'UNKNOWN' });
  const { container } = render(<React.StrictMode><AdminDashboard /></React.StrictMode>);
  expect(await screen.findByText(unknownMessage)).toBeInTheDocument();
  await act(async () => { older.resolve({ status: 'CONNECTED' }); });
  expect(container.querySelector('.integration-status-badge')).toHaveTextContent('Status not current');
  expect(screen.queryByText('Business Account')).not.toBeInTheDocument();
  expect(getGoogleStatus).toHaveBeenCalledTimes(2);
});

it('preserves staff action restrictions for UNKNOWN', async () => {
  getEffectiveRole.mockReturnValue('staff');
  getGoogleStatus.mockResolvedValue({ status: 'UNKNOWN' });
  render(<AdminDashboard />);
  expect(await screen.findByText(unknownMessage)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Connect Calendar/ })).not.toBeInTheDocument();
  expect(initiateGoogleAuth).not.toHaveBeenCalled();
});
