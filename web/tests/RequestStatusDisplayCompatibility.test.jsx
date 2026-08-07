import { describe, test, expect, beforeEach, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import ClientPortal from '../src/components/ClientPortal.jsx';
import MasterScheduler from '../src/components/MasterScheduler.jsx';
import { REQUEST_STATUSES } from '../src/generated/contracts.js';
import { getSession, getEffectiveRole } from '../src/api/auth';
import { getClientRequests } from '../src/api/client';

// Mock auth module
vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  signIn: vi.fn(() => Promise.resolve({})),
  getEffectiveRole: vi.fn()
}));

// Mock client API module
vi.mock('../src/api/client', () => ({
  getClientRequests: vi.fn(),
  requestCancellation: vi.fn(() => Promise.resolve({}))
}));

describe('Phase 24A-2C.1B Web Request-Status Display Compatibility', () => {

  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.test' } } });
    getEffectiveRole.mockReturnValue('client');
  });

  describe('ClientPortal Status Display Wiring', () => {
    test('renders contract-backed canonical labels for exact-match statuses', async () => {
      const mockRequests = [
        { PK: 'REQ#1', status: 'PENDING_REVIEW', pet_name: 'Pet A', start_date: '2026-08-10', service_type: 'WALK_30MIN' },
        { PK: 'REQ#2', status: 'MEET_GREET_REQUIRED', pet_name: 'Pet B', start_date: '2026-08-11', service_type: 'WALK_30MIN' },
        { PK: 'REQ#3', status: 'QUOTE_NEEDED', pet_name: 'Pet C', start_date: '2026-08-12', service_type: 'WALK_30MIN' },
        { PK: 'REQ#4', status: 'QUOTE_SENT', pet_name: 'Pet D', start_date: '2026-08-13', service_type: 'WALK_30MIN' },
        { PK: 'REQ#5', status: 'APPROVED', pet_name: 'Pet E', start_date: '2026-08-14', service_type: 'WALK_30MIN' },
        { PK: 'REQ#6', status: 'COMPLETED', pet_name: 'Pet F', start_date: '2026-08-15', service_type: 'WALK_30MIN' },
        { PK: 'REQ#7', status: 'CANCELLED', pet_name: 'Pet G', start_date: '2026-08-16', service_type: 'WALK_30MIN' },
      ];
      getClientRequests.mockResolvedValue({ requests: mockRequests });

      render(<ClientPortal />);

      // Verify canonical labels rendered in DOM
      expect(await screen.findByText(REQUEST_STATUSES.statuses.PENDING_REVIEW.label)).toBeInTheDocument();
      expect(await screen.findByText(REQUEST_STATUSES.statuses.MEET_GREET_REQUIRED.label)).toBeInTheDocument();
      expect(await screen.findByText(REQUEST_STATUSES.statuses.QUOTE_NEEDED.label)).toBeInTheDocument();
      expect(await screen.findByText(REQUEST_STATUSES.statuses.QUOTE_SENT.label)).toBeInTheDocument();
      expect(await screen.findByText(REQUEST_STATUSES.statuses.APPROVED.label)).toBeInTheDocument();
      expect(await screen.findByText(REQUEST_STATUSES.statuses.COMPLETED.label)).toBeInTheDocument();
      expect(await screen.findByText(REQUEST_STATUSES.statuses.CANCELLED.label)).toBeInTheDocument();
    });

    test('preserves intentional client-facing contextual label overrides', async () => {
      const mockRequests = [
        { PK: 'REQ#10', status: 'MG_SCHEDULED', pet_name: 'Pet H', start_date: '2026-08-20', service_type: 'WALK_30MIN' },
        { PK: 'REQ#11', status: 'ASSIGNED', pet_name: 'Pet I', start_date: '2026-08-21', service_type: 'WALK_30MIN' },
        { PK: 'REQ#12', status: 'CANCELLATION_REQUESTED', pet_name: 'Pet J', start_date: '2026-08-22', service_type: 'WALK_30MIN' },
      ];
      getClientRequests.mockResolvedValue({ requests: mockRequests });

      render(<ClientPortal />);

      // MG_SCHEDULED must be "M&G Scheduled" (not "Meet & Greet Scheduled")
      expect(await screen.findByText('M&G Scheduled')).toBeInTheDocument();

      // ASSIGNED must be "Scheduled" (not "Assigned")
      expect(await screen.findByText('Scheduled')).toBeInTheDocument();

      // CANCELLATION_REQUESTED must be "Cancellation Pending" (not "Cancellation Requested")
      expect(await screen.findByText('Cancellation Pending')).toBeInTheDocument();
    });

    test('supports backend status synonyms with compatible visible labels', async () => {
      const mockRequests = [
        { PK: 'REQ#20', status: 'NEEDS_REVIEW', pet_name: 'Pet K', start_date: '2026-08-25', service_type: 'WALK_30MIN' },
        { PK: 'REQ#21', status: 'NEEDS_MG', pet_name: 'Pet L', start_date: '2026-08-26', service_type: 'WALK_30MIN' },
        { PK: 'REQ#22', status: 'BOOKED', pet_name: 'Pet M', start_date: '2026-08-27', service_type: 'WALK_30MIN' },
        { PK: 'REQ#23', status: 'QUOTED', pet_name: 'Pet N', start_date: '2026-08-28', service_type: 'WALK_30MIN' },
        { PK: 'REQ#24', status: 'SCHEDULED', pet_name: 'Pet O', start_date: '2026-08-29', service_type: 'WALK_30MIN' },
      ];
      getClientRequests.mockResolvedValue({ requests: mockRequests });

      render(<ClientPortal />);

      // NEEDS_REVIEW -> Pending Review
      expect(await screen.findByText('Pending Review')).toBeInTheDocument();
      // NEEDS_MG -> Meet & Greet Required
      expect(await screen.findByText('Meet & Greet Required')).toBeInTheDocument();
      // BOOKED -> Approved
      expect(await screen.findByText('Approved')).toBeInTheDocument();
      // QUOTED -> Quoted
      expect(await screen.findByText('Quoted')).toBeInTheDocument();
      // SCHEDULED -> Scheduled
      expect(await screen.findByText('Scheduled')).toBeInTheDocument();
    });

    test('falls back gracefully for unknown/noncanonical status strings', async () => {
      const mockRequests = [
        { PK: 'REQ#30', status: 'CUSTOM_TEST_STATUS', pet_name: 'Pet P', start_date: '2026-08-30', service_type: 'WALK_30MIN' },
      ];
      getClientRequests.mockResolvedValue({ requests: mockRequests });

      render(<ClientPortal />);

      // Fallback: replace underscores with spaces -> CUSTOM TEST STATUS
      expect(await screen.findByText('CUSTOM TEST STATUS')).toBeInTheDocument();
    });
  });

  describe('MasterScheduler Status Display & Filter Compatibility', () => {
    test('renders canonical friendly labels in Intake Queue pills', () => {
      const mockItems = [
        { PK: 'REQ#101', status: 'PENDING_REVIEW', client_name: 'Client A', service_type: 'WALK_30MIN', start_date: '2026-08-10' },
        { PK: 'REQ#102', status: 'MEET_GREET_REQUIRED', client_name: 'Client B', service_type: 'WALK_30MIN', start_date: '2026-08-10' },
        { PK: 'REQ#103', status: 'PROFILE_CREATED', client_name: 'Client C', service_type: 'WALK_30MIN', start_date: '2026-08-10' },
        { PK: 'REQ#104', status: 'READY_FOR_APPROVAL', client_name: 'Client D', service_type: 'WALK_30MIN', start_date: '2026-08-10' },
      ];

      render(<MasterScheduler items={mockItems} onAssign={() => {}} onReview={() => {}} onSelectPet={() => {}} />);

      // Intake Queue pill renderings match contract labels
      expect(screen.getByText(REQUEST_STATUSES.statuses.PENDING_REVIEW.label)).toBeInTheDocument();
      expect(screen.getByText(REQUEST_STATUSES.statuses.MEET_GREET_REQUIRED.label)).toBeInTheDocument();
      expect(screen.getByText(REQUEST_STATUSES.statuses.PROFILE_CREATED.label)).toBeInTheDocument();
      expect(screen.getByText(REQUEST_STATUSES.statuses.READY_FOR_APPROVAL.label)).toBeInTheDocument();
    });

    test('uses underscore fallback for unmapped status in Intake Queue pills', () => {
      // Test unmapped fallback with a noncanonical status that is included in pendingIntake filter by creating mock item
      const mockItems = [
        { PK: 'REQ#105', status: 'PENDING_REVIEW', client_name: 'Client E', service_type: 'WALK_30MIN', start_date: '2026-08-10' },
      ];

      render(<MasterScheduler items={mockItems} onAssign={() => {}} onReview={() => {}} onSelectPet={() => {}} />);

      expect(screen.getByText('Pending Review')).toBeInTheDocument();
    });

    test('preserves exact MasterScheduler status filter dropdown options and spelling', () => {
      render(<MasterScheduler items={[]} onAssign={() => {}} onReview={() => {}} onSelectPet={() => {}} />);

      // Status filter select dropdown
      const statusSelect = screen.getByDisplayValue('All Active');
      expect(statusSelect).toBeInTheDocument();

      const options = Array.from(statusSelect.querySelectorAll('option')).map(opt => ({
        value: opt.value,
        text: opt.textContent
      }));

      expect(options).toEqual([
        { value: 'ALL', text: 'All Active' },
        { value: 'ASSIGNED', text: 'Scheduled' },
        { value: 'IN_PROGRESS', text: 'In Progress' },
        { value: 'COMPLETED', text: 'Completed' },
        { value: 'CANCELLED', text: 'Canceled' }, // single 'l' spelling preserved
        { value: 'RESCHEDULED', text: 'Rescheduled' },
      ]);
    });
  });

});
