import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

const mockGetAdminRequests = jest.fn();
const mockNavigate = jest.fn();

jest.mock('@react-navigation/native', () => {
  const React = require('react');
  return {
    useNavigation: () => ({
      navigate: mockNavigate,
      goBack: jest.fn(),
      setOptions: jest.fn(),
    }),
    useFocusEffect: (callback: () => void) => {
      React.useEffect(() => {
        callback();
      }, [callback]);
    },
  };
});

jest.mock('../src/api/client', () => ({
  getAdminRequests: (...args: unknown[]) => mockGetAdminRequests(...args),
  reviewRequest: jest.fn(),
  assignWorker: jest.fn(),
  completeJob: jest.fn(),
}));

jest.mock('../src/auth/useAuth', () => ({
  useAuth: () => ({
    logout: jest.fn(),
    role: 'owner',
    user: 'owner@example.test',
  }),
}));

jest.mock('../src/hooks/useStaff', () => ({
  useStaff: () => ({
    staff: [],
    isLoading: false,
    error: null,
    refresh: jest.fn(),
  }),
}));

jest.mock('../src/components/StatusBadge', () => ({
  StatusBadge: () => null,
}));

jest.mock('../src/components/ConfirmationModal', () => ({
  ConfirmationModal: () => null,
}));

jest.mock('../src/components/StaffPickerSheet', () => ({
  StaffPickerSheet: () => null,
}));

jest.mock('../src/components/ContentContainer', () => ({
  ContentContainer: ({ children }: { children: React.ReactNode }) => children,
}));

import { RequestCard } from '../src/components/RequestCard';
import { RequestDetailScreen } from '../src/screens/RequestDetailScreen';
import { ScheduleScreen } from '../src/screens/ScheduleScreen';
import { PetRequest } from '../src/types';

const baseRequest: PetRequest = {
  request_id: 'req-service-label',
  client_id: 'client-service-label',
  client_name: 'Synthetic Client',
  pet_name: 'Synthetic Pet',
  service_type: 'PET_SITTING',
  selected_dates: ['2099-08-01'],
  status: 'APPROVED',
  created_at: '2099-07-01',
  timeframe: 'Anytime',
  job_id: 'job-service-label',
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe('mobile service-type label owner integration', () => {
  it('renders the canonical contract label in ScheduleScreen', async () => {
    mockGetAdminRequests.mockResolvedValue([
      { ...baseRequest, service_type: 'WALK_30MIN' },
    ]);

    const view = await render(<ScheduleScreen />);

    await waitFor(() => {
      expect(view.getByText('30-Min Walk')).toBeTruthy();
    });
    expect(mockGetAdminRequests).toHaveBeenCalledWith('ALL');

    fireEvent.press(view.getByText('30-Min Walk'));
    expect(mockNavigate).toHaveBeenCalledWith('RequestDetail', expect.objectContaining({
      request: expect.objectContaining({
        service_type: 'WALK_30MIN',
      }),
      selectedDate: '2099-08-01',
      jobId: 'job-service-label',
      occurrence: expect.objectContaining({ job_id: 'job-service-label' }),
    }));
  });

  it('renders the canonical contract label in RequestDetailScreen', async () => {
    const view = await render(
      <RequestDetailScreen
        route={{
          params: {
            request: { ...baseRequest, service_type: 'DROPIN_1HR', status: 'CANCELLED' },
          },
        }}
        navigation={{ goBack: jest.fn() }}
      />
    );

    expect(view.getByText('1-Hour Drop-in')).toBeTruthy();
  });

  it('renders the canonical contract label in RequestCard', async () => {
    const request = { ...baseRequest, service_type: 'MEET_GREET', status: 'CANCELLED' };
    const view = await render(
      <RequestCard
        request={request}
        staffList={[]}
        isStaffLoading={false}
        staffError={null}
        refreshStaff={jest.fn()}
      />
    );

    expect(view.getByText('Meet & Greet')).toBeTruthy();
    fireEvent.press(view.getByText('Meet & Greet'));
    expect(mockNavigate).toHaveBeenCalledWith('RequestDetail', { request });
  });

  it('renders a noncanonical RequestCard value with exact legacy fallback output', async () => {
    const view = await render(
      <RequestCard
        request={{ ...baseRequest, service_type: 'DOG_WALKING', status: 'CANCELLED' }}
        staffList={[]}
        isStaffLoading={false}
        staffError={null}
        refreshStaff={jest.fn()}
        isDetailView
      />
    );

    expect(view.getByText('DOG WALKING')).toBeTruthy();
  });
});
