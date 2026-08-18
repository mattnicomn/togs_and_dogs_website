/**
 * Phase 24A-6: IntakeScreen Mobile Booking Intake Tests (RNTL v14)
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import {
  StyleSheet,
  View,
  Text,
  TextInput,
  TouchableOpacity,
} from 'react-native';

const mockGoBack = jest.fn();
const mockNavigate = jest.fn();

jest.mock('@react-navigation/native', () => {
  const React = require('react');
  return {
    useNavigation: () => ({
      navigate: mockNavigate,
      goBack: mockGoBack,
      setOptions: jest.fn(),
    }),
    useFocusEffect: (callback: () => void) => {
      React.useEffect(() => {
        callback();
      }, [callback]);
    },
  };
});

// Mock Auth
jest.mock('../src/auth/useAuth', () => ({
  useAuth: () => ({
    user: 'client@example.com',
    role: 'client',
    isAuthenticated: true,
    isLoading: false,
  }),
}));

// Mock API client functions
const mockGetClientPets = jest.fn();
const mockGetStaffOptions = jest.fn();
const mockSubmitClientRequest = jest.fn();

jest.mock('../src/api/client', () => ({
  getClientPets: (...args: any[]) => mockGetClientPets(...args),
  getStaffOptions: (...args: any[]) => mockGetStaffOptions(...args),
  submitClientRequest: (...args: any[]) => mockSubmitClientRequest(...args),
}));

import { IntakeScreen } from '../src/screens/IntakeScreen';
import { SERVICE_TYPES } from '../src/contracts/generatedContracts';

describe('IntakeScreen Component Tests', () => {
  const selectDefaultWalkWindow = async () => {
    await fireEvent.press(screen.getByLabelText('Morning, 6:30 AM to 9:30 AM'));
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetClientPets.mockResolvedValue([
      { id: 'PET-1', name: 'Buster', species: 'DOG', breed: 'Golden Retriever' },
      { id: 'PET-2', name: 'Luna', species: 'CAT', breed: 'Siamese' },
    ]);
    mockGetStaffOptions.mockResolvedValue({
      staff_options: [{ id: 'STAFF-1', name: 'Sitter Sarah' }],
    });
    mockSubmitClientRequest.mockResolvedValue({ request_id: 'REQ-12345' });
  });

  test('1. renders Step 1 with service options and schedule selector', async () => {
    await render(<IntakeScreen />);

    await waitFor(() => {
      expect(screen.getByText('Book Pet Care')).toBeTruthy();
      expect(screen.getByText('1. Select Service')).toBeTruthy();
    });
  });

  test('2. derives exactly 3 target intake service options from canonical booking eligibility', async () => {
    const canonicalIntakeServices = Object.entries(SERVICE_TYPES.services)
      .filter(([, service]) => (
        service.supportedOnMobile === true
        && service.lifecycle === 'active'
        && service.newBookingEligibility === 'eligible'
      ));

    expect(canonicalIntakeServices.map(([key]) => key)).toEqual([
      'WALK_20MIN',
      'CHECK_IN',
      'OVERNIGHT',
    ]);

    await render(<IntakeScreen />);

    await waitFor(() => {
      canonicalIntakeServices.forEach(([, service]) => {
        expect(screen.getByText(service.labelLong)).toBeTruthy();
      });
    });
  });

  test('3. excludes legacy and non-new-booking services from customer intake UI', async () => {
    const unavailableForNewBookings = [
      SERVICE_TYPES.services.WALK_30MIN,
      SERVICE_TYPES.services.WALK_60MIN,
      SERVICE_TYPES.services.DROPIN_1HR,
      SERVICE_TYPES.services.DROPIN_3HR,
      SERVICE_TYPES.services.PET_SITTING,
      SERVICE_TYPES.services.MEET_GREET,
    ];
    unavailableForNewBookings.forEach((service) => {
      expect(service.newBookingEligibility).not.toBe('eligible');
    });

    await render(<IntakeScreen />);

    await waitFor(() => {
      unavailableForNewBookings.forEach((service) => {
        expect(screen.queryByText(service.labelLong)).toBeNull();
      });
    });
  });

  test('4. validates step 1 required fields (date selection required)', async () => {
    await render(<IntakeScreen />);
    await selectDefaultWalkWindow();

    await waitFor(() => {
      expect(screen.getByText('Continue →')).toBeTruthy();
      expect(screen.getByLabelText('Continue →')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('⚠️ Please select at least one visit date.')).toBeTruthy();
    });
  });

  test('5. progresses to Step 2 after valid date selection', async () => {
    await render(<IntakeScreen />);
    await selectDefaultWalkWindow();

    const dateChips = await screen.findAllByLabelText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    expect(dateChips.length).toBeGreaterThan(0);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });
  });

  test('6. loads existing read-only client pets from getClientPets', async () => {
    await render(<IntakeScreen />);

    const dateChips = await screen.findAllByLabelText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(mockGetClientPets).toHaveBeenCalled();
    });
  });

  test('7. validates terms acceptance before submission on Step 3', async () => {
    await render(<IntakeScreen />);
    await selectDefaultWalkWindow();

    const dateChips = await screen.findAllByLabelText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);
    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    const submitBtn = screen.getByLabelText('Submit Booking Request');
    expect(submitBtn.props.accessibilityState.disabled).toBe(true);

    fireEvent.press(submitBtn);

    expect(mockSubmitClientRequest).not.toHaveBeenCalled();
  });

  test('8. submits valid care-request payload without client-assigned status', async () => {
    mockSubmitClientRequest.mockResolvedValue({ request_id: 'REQ-998877' });

    await render(<IntakeScreen />);
    await selectDefaultWalkWindow();

    const dateChips = await screen.findAllByLabelText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('I accept the Tog & Dogs Terms of Service and Privacy Policy.'));
    await waitFor(() => {
      expect(screen.getByText('☑')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Submit Booking Request'));

    await waitFor(() => {
      expect(mockSubmitClientRequest).toHaveBeenCalledTimes(1);
      const submittedPayload = mockSubmitClientRequest.mock.calls[0][0];

      expect(submittedPayload.client_email).toBe('client@example.com');
      expect(submittedPayload.client_name).toBeTruthy();
      expect(submittedPayload.service_type).toBe('WALK_20MIN');
      expect(submittedPayload.visits_per_day).toBeUndefined();
      expect(submittedPayload.visit_windows).toEqual(['MORNING']);
      expect(Array.isArray(submittedPayload.selected_dates)).toBe(true);
      expect(submittedPayload.selected_dates.length).toBeGreaterThan(0);
      expect(submittedPayload.start_date).toBeTruthy();
      expect(submittedPayload.accepted_terms).toBe(true);
      expect(submittedPayload.accepted_privacy).toBe(true);
      expect(submittedPayload.terms_version).toBe('1.0');
      expect(submittedPayload.privacy_version).toBe('1.0');
      expect(submittedPayload.status).toBeUndefined();
    });

    await waitFor(() => {
      expect(screen.getByText('Request Received!')).toBeTruthy();
      expect(screen.getByText('REQ-998877')).toBeTruthy();
    });
  });

  test('9. handles API submission error gracefully', async () => {
    mockSubmitClientRequest.mockRejectedValue(new Error('Network error: Unable to connect'));

    await render(<IntakeScreen />);
    await selectDefaultWalkWindow();

    const dateChips = await screen.findAllByLabelText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('I accept the Tog & Dogs Terms of Service and Privacy Policy.'));
    await waitFor(() => {
      expect(screen.getByText('☑')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Submit Booking Request'));

    await waitFor(() => {
      expect(screen.getByText('⚠️ Network error: Unable to connect')).toBeTruthy();
    });
  });

  test('10. navigates back when View My Bookings is pressed', async () => {
    mockSubmitClientRequest.mockResolvedValue({ request_id: 'REQ-112233' });

    await render(<IntakeScreen />);
    await selectDefaultWalkWindow();

    const dateChips = await screen.findAllByLabelText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('I accept the Tog & Dogs Terms of Service and Privacy Policy.'));
    await waitFor(() => {
      expect(screen.getByText('☑')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Submit Booking Request'));

    await waitFor(() => {
      expect(screen.getByText('View My Bookings')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('View My Bookings'));
    expect(mockNavigate).toHaveBeenCalledWith('ClientTabs', { screen: 'Bookings' });
    expect(mockNavigate).not.toHaveBeenCalledWith('Bookings');
  });

  test('11. exposes accessibility roles and selection states on intake controls', async () => {
    await render(<IntakeScreen />);

    await waitFor(() => {
      const walkOption = screen.getByLabelText('Select service 20-Minute Walk');
      expect(walkOption.props.accessibilityRole).toBe('button');
      expect(walkOption.props.accessibilityState.selected).toBe(true);
    });

    const dateChips = await screen.findAllByLabelText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    expect(dateChips[0].props.accessibilityRole).toBe('button');
    expect(dateChips[0].props.accessibilityState.selected).toBe(false);

    fireEvent.press(dateChips[0]);
    await waitFor(() => {
      expect(dateChips[0].props.accessibilityState.selected).toBe(true);
    });

    await fireEvent.press(screen.getByLabelText('Select service 30-Minute Check-In'));
    const visitsOption = screen.getByLabelText('1 visit per day');
    expect(visitsOption.props.accessibilityRole).toBe('button');
    expect(visitsOption.props.accessibilityState.selected).toBe(false);

    await fireEvent.press(visitsOption);
    const windowOption = screen.getByLabelText('Morning, 6:30 AM to 9:30 AM');
    expect(windowOption.props.accessibilityRole).toBe('button');
    expect(windowOption.props.accessibilityState.selected).toBe(false);
    expect(windowOption.props.accessibilityState.disabled).toBe(false);

    await fireEvent.press(windowOption);
    expect(windowOption.props.accessibilityState.selected).toBe(true);
  });

  test('12. exposes checkbox role and checked accessibility state on policy agreement row', async () => {
    await render(<IntakeScreen />);
    await selectDefaultWalkWindow();

    const dateChips = await screen.findAllByLabelText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);
    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    const checkbox = screen.getByLabelText('Accept Tog & Dogs Terms of Service and Privacy Policy');
    expect(checkbox.props.accessibilityRole).toBe('checkbox');
    expect(checkbox.props.accessibilityState.checked).toBe(false);

    fireEvent.press(checkbox);
    await waitFor(() => {
      expect(checkbox.props.accessibilityState.checked).toBe(true);
    });
  });

  test('13. exposes disabled accessibility state on submit button when terms unaccepted', async () => {
    await render(<IntakeScreen />);
    await selectDefaultWalkWindow();

    const dateChips = await screen.findAllByLabelText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);
    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });
    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    const submitBtn = screen.getByLabelText('Submit Booking Request');
    expect(submitBtn.props.accessibilityRole).toBe('button');
    expect(submitBtn.props.accessibilityState.disabled).toBe(true);
  });

  test('14. exposes confirmation screen header and accessible action button', async () => {
    mockSubmitClientRequest.mockResolvedValue({ request_id: 'REQ-778899' });

    await render(<IntakeScreen />);
    await selectDefaultWalkWindow();

    const dateChips = await screen.findAllByLabelText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);
    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });
    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByLabelText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('I accept the Tog & Dogs Terms of Service and Privacy Policy.'));
    await waitFor(() => {
      expect(screen.getByText('☑')).toBeTruthy();
    });

    const submitBtn = screen.getByLabelText('Submit Booking Request');
    expect(submitBtn.props.accessibilityState.disabled).toBe(false);

    fireEvent.press(submitBtn);

    await waitFor(() => {
      const successTitle = screen.getByText('Request Received!');
      expect(successTitle.props.accessibilityRole).toBe('header');
      expect(screen.getByText('View My Bookings')).toBeTruthy();
    });
  });
});

describe('IntakeScreen - Ryan Slice D2 Check-In intake parity', () => {
  const dateLabelPattern = /^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/;
  const morningLabel = 'Morning, 6:30 AM to 9:30 AM';
  const middayLabel = 'Mid-day, 10:30 AM to 3:30 PM';
  const eveningLabel = 'Evening, 6:00 PM to 9:30 PM';

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetClientPets.mockResolvedValue([
      { id: 'PET-1', name: 'Buster', species: 'DOG', breed: 'Golden Retriever' },
    ]);
    mockGetStaffOptions.mockResolvedValue({ staff_options: [] });
    mockSubmitClientRequest.mockResolvedValue({ request_id: 'REQ-D2' });
  });

  const selectCheckIn = async () => {
    await fireEvent.press(screen.getByLabelText('Select service 30-Minute Check-In'));
  };

  const selectFirstDate = async () => {
    const dateChips = await screen.findAllByLabelText(dateLabelPattern);
    await fireEvent.press(dateChips[0]);
    await screen.findByText(/Selected \(1\)/);
  };

  const advanceToReview = async () => {
    await fireEvent.press(screen.getByLabelText('Continue →'));
    await screen.findByText('Select Pets');
    await screen.findByText(/Buster/);
    await fireEvent.press(screen.getByLabelText('Continue →'));
    await screen.findByText('Review Booking Request');
  };

  const submitReviewedRequest = async () => {
    await fireEvent.press(screen.getByLabelText('Accept Tog & Dogs Terms of Service and Privacy Policy'));
    await fireEvent.press(screen.getByLabelText('Submit Booking Request'));
    await waitFor(() => expect(mockSubmitClientRequest).toHaveBeenCalledTimes(1));
    return mockSubmitClientRequest.mock.calls[0][0];
  };

  test('derives Check-In count/window controls and display metadata from the canonical contract', async () => {
    await render(<IntakeScreen />);
    await selectCheckIn();

    expect(SERVICE_TYPES.services.CHECK_IN.visitsPerDayOptions).toEqual([1, 2, 3]);
    expect(SERVICE_TYPES.services.CHECK_IN.allowedWindowIds).toEqual(['MORNING', 'MIDDAY', 'EVENING']);
    expect(SERVICE_TYPES.services.CHECK_IN.durationMinutes).toBe(30);

    SERVICE_TYPES.services.CHECK_IN.visitsPerDayOptions.forEach((count) => {
      const control = screen.getByLabelText(`${count} visit${count === 1 ? '' : 's'} per day`);
      expect(control.props.accessibilityRole).toBe('button');
      expect(control.props.accessibilityState.selected).toBe(false);
    });

    [morningLabel, middayLabel, eveningLabel].forEach((label) => {
      const control = screen.getByLabelText(label);
      expect(control.props.accessibilityRole).toBe('button');
      expect(control.props.accessibilityState.disabled).toBe(true);
    });
    expect(screen.queryByLabelText(/Afternoon/i)).toBeNull();
    expect(screen.queryByLabelText(/Any.?time/i)).toBeNull();
  });

  test('submits a valid 1/day Check-In with one canonical window and review summary', async () => {
    await render(<IntakeScreen />);
    await selectCheckIn();
    await fireEvent.press(screen.getByLabelText('1 visit per day'));
    await fireEvent.press(screen.getByLabelText(morningLabel));
    await selectFirstDate();
    await advanceToReview();

    expect(screen.getByText('Check-In')).toBeTruthy();
    expect(screen.getByText('30 minutes')).toBeTruthy();
    expect(screen.getByText('Visits per day:')).toBeTruthy();
    expect(screen.getByText('1')).toBeTruthy();
    expect(screen.getByText('Visit windows:')).toBeTruthy();
    expect(screen.getByText('Morning')).toBeTruthy();

    const payload = await submitReviewedRequest();
    expect(payload).toEqual(expect.objectContaining({
      service_type: 'CHECK_IN',
      visits_per_day: 1,
      visit_windows: ['MORNING'],
      selected_dates: [expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/)],
      accepted_terms: true,
      accepted_privacy: true,
    }));
    expect(payload.visit_window).toBeUndefined();
    expect(payload.status).toBeUndefined();
  });

  test('caps 2/day Check-In at two distinct windows and submits canonical order', async () => {
    await render(<IntakeScreen />);
    await selectCheckIn();
    await fireEvent.press(screen.getByLabelText('2 visits per day'));
    await fireEvent.press(screen.getByLabelText(eveningLabel));
    await fireEvent.press(screen.getByLabelText(morningLabel));

    const midday = screen.getByLabelText(middayLabel);
    expect(midday.props.accessibilityState.selected).toBe(false);
    expect(midday.props.accessibilityState.disabled).toBe(true);
    await fireEvent.press(midday);
    expect(midday.props.accessibilityState.selected).toBe(false);

    await selectFirstDate();
    await advanceToReview();
    expect(screen.getByText('Morning, Evening')).toBeTruthy();

    const payload = await submitReviewedRequest();
    expect(payload.visits_per_day).toBe(2);
    expect(payload.visit_windows).toEqual(['MORNING', 'EVENING']);
    expect(new Set(payload.visit_windows).size).toBe(2);
  });

  test('auto-selects all canonical windows for a 3/day Check-In', async () => {
    await render(<IntakeScreen />);
    await selectCheckIn();
    await fireEvent.press(screen.getByLabelText('3 visits per day'));

    [morningLabel, middayLabel, eveningLabel].forEach((label) => {
      const control = screen.getByLabelText(label);
      expect(control.props.accessibilityState.selected).toBe(true);
      expect(control.props.accessibilityState.disabled).toBe(true);
    });
    expect(screen.getByText('All three daily windows are used automatically.')).toBeTruthy();

    await selectFirstDate();
    await advanceToReview();
    expect(screen.getByText('Morning, Mid-day, Evening')).toBeTruthy();

    const payload = await submitReviewedRequest();
    expect(payload.visits_per_day).toBe(3);
    expect(payload.visit_windows).toEqual(['MORNING', 'MIDDAY', 'EVENING']);
  });

  test('requires a visit count and the exact number of windows before continuing', async () => {
    await render(<IntakeScreen />);
    await selectCheckIn();
    await fireEvent.press(screen.getByLabelText('Continue →'));
    expect(await screen.findByText('⚠️ Choose how many visits you need each day.')).toBeTruthy();

    await fireEvent.press(screen.getByLabelText('2 visits per day'));
    await fireEvent.press(screen.getByLabelText(morningLabel));
    await fireEvent.press(screen.getByLabelText('Continue →'));
    expect(await screen.findByText('⚠️ Choose 2 visit windows.')).toBeTruthy();

    await fireEvent.press(screen.getByLabelText(morningLabel));
    expect(screen.getByLabelText(morningLabel).props.accessibilityState.selected).toBe(false);
    await fireEvent.press(screen.getByLabelText(morningLabel));
    expect(screen.getByLabelText(morningLabel).props.accessibilityState.selected).toBe(true);
  });

  test('normalizes window state safely across 2 to 1 to 3 visit transitions', async () => {
    await render(<IntakeScreen />);
    await selectCheckIn();
    await fireEvent.press(screen.getByLabelText('2 visits per day'));
    await fireEvent.press(screen.getByLabelText(morningLabel));
    await fireEvent.press(screen.getByLabelText(eveningLabel));

    await fireEvent.press(screen.getByLabelText('1 visit per day'));
    expect(screen.getByLabelText(morningLabel).props.accessibilityState.selected).toBe(true);
    expect(screen.getByLabelText(eveningLabel).props.accessibilityState.selected).toBe(false);

    await fireEvent.press(screen.getByLabelText('3 visits per day'));
    [morningLabel, middayLabel, eveningLabel].forEach((label) => {
      expect(screen.getByLabelText(label).props.accessibilityState.selected).toBe(true);
    });
  });

  test('clears Check-In state when switching to Walk and when switching back', async () => {
    await render(<IntakeScreen />);
    await selectCheckIn();
    await fireEvent.press(screen.getByLabelText('2 visits per day'));
    await fireEvent.press(screen.getByLabelText(morningLabel));
    await fireEvent.press(screen.getByLabelText(eveningLabel));
    await fireEvent.press(screen.getByLabelText('Select service 20-Minute Walk'));

    expect(screen.queryByText('2. Visits per day')).toBeNull();
    await fireEvent.press(screen.getByLabelText('Select service 30-Minute Check-In'));
    expect(screen.getByLabelText('2 visits per day').props.accessibilityState.selected).toBe(false);
    expect(screen.getByLabelText(morningLabel).props.accessibilityState.selected).toBe(false);

    await fireEvent.press(screen.getByLabelText('Select service 20-Minute Walk'));
    await fireEvent.press(screen.getByLabelText(morningLabel));
    await selectFirstDate();
    await advanceToReview();
    expect(screen.getByText('20-Min Walk')).toBeTruthy();
    expect(screen.getByText('20 minutes')).toBeTruthy();

    const payload = await submitReviewedRequest();
    expect(payload.service_type).toBe('WALK_20MIN');
    expect(payload.visits_per_day).toBeUndefined();
    expect(payload.visit_windows).toEqual(['MORNING']);
  });

  test('renders and submits the contract-owned fixed Overnight schedule without client scheduling fields', async () => {
    await render(<IntakeScreen />);
    await selectCheckIn();
    await fireEvent.press(screen.getByLabelText('3 visits per day'));
    await fireEvent.press(screen.getByLabelText('Select service Overnight Care'));

    expect(screen.queryByText('2. Visits per day')).toBeNull();
    expect(screen.queryByLabelText(morningLabel)).toBeNull();
    expect(screen.getByLabelText('Fixed Overnight schedule 9:00 PM–7:00 AM. Ends the following morning.')).toBeTruthy();
    expect(screen.getByText('Each selected date is the night service starts. Ends the following morning.')).toBeTruthy();
    expect(screen.getByText('10 hours nominal service.')).toBeTruthy();
    await selectFirstDate();
    await advanceToReview();
    expect(screen.getByText('Overnight Care')).toBeTruthy();
    expect(screen.getByText('10 hours')).toBeTruthy();
    expect(screen.getByText('9:00 PM–7:00 AM next morning')).toBeTruthy();
    expect(screen.getByText(/Overnight start dates/)).toBeTruthy();
    expect(screen.queryByText('Visits per day:')).toBeNull();

    const payload = await submitReviewedRequest();
    expect(payload.service_type).toBe('OVERNIGHT');
    [
      'visits_per_day', 'visit_windows', 'visit_window', 'preferred_time', 'scheduled_time',
      'start_time', 'end_time', 'fixed_start_time', 'fixed_end_time', 'scheduled_duration'
    ].forEach(field => expect(payload[field]).toBeUndefined());
  });

  test('clears incompatible state across Check-In, Overnight, Walk, and Overnight transitions', async () => {
    await render(<IntakeScreen />);
    await selectCheckIn();
    await fireEvent.press(screen.getByLabelText('2 visits per day'));
    await fireEvent.press(screen.getByLabelText(morningLabel));
    await fireEvent.press(screen.getByLabelText(eveningLabel));

    await fireEvent.press(screen.getByLabelText('Select service Overnight Care'));
    expect(screen.queryByText('2. Visits per day')).toBeNull();
    expect(screen.queryByLabelText(morningLabel)).toBeNull();

    await fireEvent.press(screen.getByLabelText('Select service 20-Minute Walk'));
    expect(screen.getByLabelText(morningLabel).props.accessibilityState.checked).toBe(false);
    await fireEvent.press(screen.getByLabelText(eveningLabel));

    await fireEvent.press(screen.getByLabelText('Select service Overnight Care'));
    expect(screen.queryByLabelText(eveningLabel)).toBeNull();
    await fireEvent.press(screen.getByLabelText('Select service 30-Minute Check-In'));
    expect(screen.getByLabelText('2 visits per day').props.accessibilityState.selected).toBe(false);
    expect(screen.getByLabelText(eveningLabel).props.accessibilityState.selected).toBe(false);
  });
});

describe('IntakeScreen - Ryan W1 Walk canonical scheduling', () => {
  const dateLabelPattern = /^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/;
  const morningLabel = 'Morning, 6:30 AM to 9:30 AM';
  const middayLabel = 'Mid-day, 10:30 AM to 3:30 PM';
  const eveningLabel = 'Evening, 6:00 PM to 9:30 PM';

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetClientPets.mockResolvedValue([
      { id: 'PET-1', name: 'Buster', species: 'DOG', breed: 'Golden Retriever' },
    ]);
    mockGetStaffOptions.mockResolvedValue({ staff_options: [] });
    mockSubmitClientRequest.mockResolvedValue({ request_id: 'REQ-W1' });
  });

  const selectDateAndAdvanceToReview = async () => {
    const dateChips = await screen.findAllByLabelText(dateLabelPattern);
    await fireEvent.press(dateChips[0]);
    await fireEvent.press(screen.getByLabelText('Continue →'));
    await screen.findByText('Select Pets');
    await screen.findByText(/Buster/);
    await fireEvent.press(screen.getByLabelText('Continue →'));
    await screen.findByText('Review Booking Request');
  };

  test('derives three exactly-one Walk radios and canonical ranges from the generated contract', async () => {
    await render(<IntakeScreen />);

    expect(SERVICE_TYPES.services.WALK_20MIN.durationMinutes).toBe(20);
    expect(SERVICE_TYPES.services.WALK_20MIN.windowSelectionMode).toBe('exactly_one');
    expect(SERVICE_TYPES.services.WALK_20MIN.allowedWindowIds).toEqual(['MORNING', 'MIDDAY', 'EVENING']);
    [morningLabel, middayLabel, eveningLabel].forEach((label) => {
      const control = screen.getByLabelText(label);
      expect(control.props.accessibilityRole).toBe('radio');
      expect(control.props.accessibilityState.selected).toBe(false);
      expect(control.props.accessibilityState.checked).toBe(false);
    });
    expect(screen.queryByText('2. Visits per day')).toBeNull();
  });

  test('requires one Walk window and atomically replaces Morning with Mid-day then Evening', async () => {
    await render(<IntakeScreen />);
    await fireEvent.press(screen.getByLabelText('Continue →'));
    expect(await screen.findByText('⚠️ Choose exactly one visit window.')).toBeTruthy();

    await fireEvent.press(screen.getByLabelText(morningLabel));
    expect(screen.getByLabelText(morningLabel).props.accessibilityState.checked).toBe(true);
    await fireEvent.press(screen.getByLabelText(middayLabel));
    expect(screen.getByLabelText(morningLabel).props.accessibilityState.checked).toBe(false);
    expect(screen.getByLabelText(middayLabel).props.accessibilityState.checked).toBe(true);
    await fireEvent.press(screen.getByLabelText(eveningLabel));
    expect(screen.getByLabelText(middayLabel).props.accessibilityState.checked).toBe(false);
    expect(screen.getByLabelText(eveningLabel).props.accessibilityState.checked).toBe(true);
  });

  test('reviews and submits one canonical Walk window without visits_per_day', async () => {
    await render(<IntakeScreen />);
    await fireEvent.press(screen.getByLabelText(middayLabel));
    await selectDateAndAdvanceToReview();

    expect(screen.getByText('20-Min Walk')).toBeTruthy();
    expect(screen.getByText('20 minutes')).toBeTruthy();
    expect(screen.getByText('Visit window:')).toBeTruthy();
    expect(screen.getByText('Mid-day (10:30 AM–3:30 PM)')).toBeTruthy();
    expect(screen.queryByText('Visits per day:')).toBeNull();

    await fireEvent.press(screen.getByLabelText('Accept Tog & Dogs Terms of Service and Privacy Policy'));
    await fireEvent.press(screen.getByLabelText('Submit Booking Request'));
    await waitFor(() => expect(mockSubmitClientRequest).toHaveBeenCalledTimes(1));
    const payload = mockSubmitClientRequest.mock.calls[0][0];
    expect(payload.service_type).toBe('WALK_20MIN');
    expect(payload.visit_windows).toEqual(['MIDDAY']);
    expect(payload.visits_per_day).toBeUndefined();
    expect(payload.visit_window).toBeUndefined();
  });

  test('clears incompatible state across Walk, Check-In, Overnight, and Walk transitions', async () => {
    await render(<IntakeScreen />);
    await fireEvent.press(screen.getByLabelText(eveningLabel));
    await fireEvent.press(screen.getByLabelText('Select service 30-Minute Check-In'));
    expect(screen.getByLabelText('1 visit per day').props.accessibilityState.selected).toBe(false);
    expect(screen.getByLabelText(eveningLabel).props.accessibilityState.selected).toBe(false);

    await fireEvent.press(screen.getByLabelText('2 visits per day'));
    await fireEvent.press(screen.getByLabelText(morningLabel));
    await fireEvent.press(screen.getByLabelText(eveningLabel));
    await fireEvent.press(screen.getByLabelText('Select service Overnight Care'));
    expect(screen.queryByLabelText(morningLabel)).toBeNull();
    expect(screen.queryByText('2. Visits per day')).toBeNull();

    await fireEvent.press(screen.getByLabelText('Select service 20-Minute Walk'));
    expect(screen.getByLabelText(morningLabel).props.accessibilityState.checked).toBe(false);
    expect(screen.getByLabelText(middayLabel).props.accessibilityState.checked).toBe(false);
    expect(screen.getByLabelText(eveningLabel).props.accessibilityState.checked).toBe(false);
  });
});

describe('IntakeScreen - Phase 24A-9C.1 Keyboard Structure', () => {
  it('wraps the intake form in keyboard-aware scroll structure', async () => {
    await render(<IntakeScreen />);
    await screen.findByText('Book Pet Care');

    const keyboardView = screen.getByTestId('intake-keyboard-container');
    const scrollView = screen.getByTestId('intake-form-scroll');
    expect(keyboardView.props.behavior).not.toBe('height');
    expect(scrollView.props.keyboardShouldPersistTaps).toBe('handled');
    expect(StyleSheet.flatten(scrollView.props.contentContainerStyle).paddingBottom).toBe(120);
  });
});
