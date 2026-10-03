/**
 * OPS-2A — RequestCard client-side role gating reconciliation.
 *
 * Backend RBAC is authoritative: Approve is an owner/admin-only sensitive
 * /admin/review transition and staff assignment is owner/admin-only (/admin/assign).
 * RequestCard mirrors RequestDetailScreen by gating Approve / Assign / Change on an
 * explicit owner/admin allowlist (canManage = role === 'owner' || role === 'admin').
 *
 * The runtime role domain at this surface is owner | staff | client | unknown | null
 * (AuthContext role is `string | null`; getEffectiveRole yields owner/staff/client/
 * unknown; role is null during bootstrap). A permissive `role !== 'staff'` gate would
 * fail open for client/unknown/null, so these tests prove the allowlist fails closed
 * for every non-manager role, including client and unknown/null.
 */
import React from 'react';
import { render } from '@testing-library/react-native';

const mockNavigate = jest.fn();
let mockRole: string | null = 'owner';

jest.mock('@react-navigation/native', () => {
  const React = require('react');
  return {
    useNavigation: () => ({ navigate: mockNavigate }),
    useFocusEffect: (callback: () => void) => {
      React.useEffect(() => callback(), [callback]);
    },
  };
});
jest.mock('../src/api/client', () => ({
  reviewRequest: jest.fn(),
  assignWorker: jest.fn(),
}));
jest.mock('../src/auth/useAuth', () => ({ useAuth: () => ({ role: mockRole, logout: jest.fn() }) }));
jest.mock('../src/components/StatusBadge', () => ({ StatusBadge: () => null }));
jest.mock('../src/components/StaffPickerSheet', () => ({ StaffPickerSheet: () => null }));
jest.mock('../src/components/ConfirmationModal', () => ({ ConfirmationModal: () => null }));

import { RequestCard } from '../src/components/RequestCard';

const baseProps = {
  staffList: [],
  isStaffLoading: false,
  staffError: null,
  refreshStaff: jest.fn(),
  onApproveSuccess: jest.fn(),
  defaultExpanded: true, // action buttons render inside the expanded content
};
const req = (status: string) => ({
  request_id: 'r', client_id: 'c', client_name: 'Client', pet_name: 'Pet',
  service_type: 'DROPIN_1HR', selected_dates: ['2026-09-01'], status, created_at: 'x',
});

beforeEach(() => {
  jest.clearAllMocks();
  mockRole = 'owner';
});

describe('RequestCard role gating — owner/admin see actions', () => {
  it('owner sees Approve on a pending request', async () => {
    mockRole = 'owner';
    const view = await render(<RequestCard {...baseProps} request={req('PENDING_REVIEW') as any} />);
    expect(view.getByText('Approve Booking')).toBeTruthy();
  });
  it('owner sees Assign Staff on an approved request', async () => {
    mockRole = 'owner';
    const view = await render(<RequestCard {...baseProps} request={req('APPROVED') as any} />);
    expect(view.getByText('Assign Staff')).toBeTruthy();
  });
  it('owner sees Change Staff on an assigned request', async () => {
    mockRole = 'owner';
    const view = await render(<RequestCard {...baseProps} request={req('ASSIGNED') as any} />);
    expect(view.getByText('Change Staff')).toBeTruthy();
  });
  it('admin sees Approve on a pending request', async () => {
    mockRole = 'admin';
    const view = await render(<RequestCard {...baseProps} request={req('PENDING_REVIEW') as any} />);
    expect(view.getByText('Approve Booking')).toBeTruthy();
  });
});

describe('RequestCard role gating — staff see no owner/admin actions', () => {
  it('staff sees NO Approve on a pending request', async () => {
    mockRole = 'staff';
    const view = await render(<RequestCard {...baseProps} request={req('PENDING_REVIEW') as any} />);
    expect(view.queryByText('Approve Booking')).toBeNull();
  });
  it('staff sees NO Assign Staff on an approved request', async () => {
    mockRole = 'staff';
    const view = await render(<RequestCard {...baseProps} request={req('APPROVED') as any} />);
    expect(view.queryByText('Assign Staff')).toBeNull();
  });
  it('staff sees NO Change Staff on an assigned request', async () => {
    mockRole = 'staff';
    const view = await render(<RequestCard {...baseProps} request={req('ASSIGNED') as any} />);
    expect(view.queryByText('Change Staff')).toBeNull();
  });
});

describe('RequestCard role gating — non-manager roles fail closed (allowlist)', () => {
  it('client sees NO Approve on a pending request', async () => {
    mockRole = 'client';
    const view = await render(<RequestCard {...baseProps} request={req('PENDING_REVIEW') as any} />);
    expect(view.queryByText('Approve Booking')).toBeNull();
  });
  it('client sees NO Assign Staff on an approved request', async () => {
    mockRole = 'client';
    const view = await render(<RequestCard {...baseProps} request={req('APPROVED') as any} />);
    expect(view.queryByText('Assign Staff')).toBeNull();
  });
  it('unknown role sees NO Approve on a pending request', async () => {
    mockRole = 'unknown';
    const view = await render(<RequestCard {...baseProps} request={req('PENDING_REVIEW') as any} />);
    expect(view.queryByText('Approve Booking')).toBeNull();
  });
  it('null role (bootstrap) sees NO Approve on a pending request', async () => {
    mockRole = null;
    const view = await render(<RequestCard {...baseProps} request={req('PENDING_REVIEW') as any} />);
    expect(view.queryByText('Approve Booking')).toBeNull();
  });
});
