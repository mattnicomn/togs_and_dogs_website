/**
 * Phase 24A-6: IntakeScreen Mobile Booking Intake Tests (RNTL v14)
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { View, Text, TextInput, TouchableOpacity } from 'react-native';

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

  test('2. derives exactly 6 canonical intake service options from SERVICE_TYPES contract', async () => {
    const canonicalIntakeServices = Object.entries(SERVICE_TYPES.services)
      .filter(([, s]) => s.availableInIntake === true);

    expect(canonicalIntakeServices.length).toBe(6);

    await render(<IntakeScreen />);

    await waitFor(() => {
      expect(screen.getByText('30-Min Walk')).toBeTruthy();
      expect(screen.getByText('60-Min Walk')).toBeTruthy();
      expect(screen.getByText('1-Hour Drop-in')).toBeTruthy();
      expect(screen.getByText('3-Hour Drop-in')).toBeTruthy();
      expect(screen.getByText('Overnight Care')).toBeTruthy();
      expect(screen.getByText('Pet Sitting')).toBeTruthy();
    });
  });

  test('3. excludes MEET_GREET service option from customer intake UI', async () => {
    const meetGreetConfig = SERVICE_TYPES.services.MEET_GREET;
    expect(meetGreetConfig.availableInIntake).toBe(false);

    await render(<IntakeScreen />);

    await waitFor(() => {
      expect(screen.queryByText('Meet & Greet')).toBeNull();
    });
  });

  test('4. validates step 1 required fields (date selection required)', async () => {
    await render(<IntakeScreen />);

    await waitFor(() => {
      expect(screen.getByText('Continue →')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('⚠️ Please select at least one visit date.')).toBeTruthy();
    });
  });

  test('5. progresses to Step 2 after valid date selection', async () => {
    await render(<IntakeScreen />);

    const dateChips = await screen.findAllByText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    expect(dateChips.length).toBeGreaterThan(0);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });
  });

  test('6. loads existing read-only client pets from getClientPets', async () => {
    await render(<IntakeScreen />);

    const dateChips = await screen.findAllByText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(mockGetClientPets).toHaveBeenCalled();
    });
  });

  test('7. validates terms acceptance before submission on Step 3', async () => {
    await render(<IntakeScreen />);

    const dateChips = await screen.findAllByText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Submit Booking Request'));

    await waitFor(() => {
      expect(screen.getByText('⚠️ You must accept the Terms and Privacy Policy before submitting.')).toBeTruthy();
      expect(mockSubmitClientRequest).not.toHaveBeenCalled();
    });
  });

  test('8. submits valid care-request payload without client-assigned status', async () => {
    mockSubmitClientRequest.mockResolvedValue({ request_id: 'REQ-998877' });

    await render(<IntakeScreen />);

    const dateChips = await screen.findAllByText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('I accept the Tog & Dogs Terms of Service and Privacy Policy.'));
    await waitFor(() => {
      expect(screen.getByText('☑')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Submit Booking Request'));

    await waitFor(() => {
      expect(mockSubmitClientRequest).toHaveBeenCalledTimes(1);
      const submittedPayload = mockSubmitClientRequest.mock.calls[0][0];

      expect(submittedPayload.client_email).toBe('client@example.com');
      expect(submittedPayload.client_name).toBeTruthy();
      expect(submittedPayload.service_type).toBe('PET_SITTING');
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

    const dateChips = await screen.findAllByText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('I accept the Tog & Dogs Terms of Service and Privacy Policy.'));
    await waitFor(() => {
      expect(screen.getByText('☑')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Submit Booking Request'));

    await waitFor(() => {
      expect(screen.getByText('⚠️ Network error: Unable to connect')).toBeTruthy();
    });
  });

  test('10. navigates back when View My Bookings is pressed', async () => {
    mockSubmitClientRequest.mockResolvedValue({ request_id: 'REQ-112233' });

    await render(<IntakeScreen />);

    const dateChips = await screen.findAllByText(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
    fireEvent.press(dateChips[0]);

    await waitFor(() => {
      expect(screen.getByText(/Selected \(1\)/)).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Select Pets')).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText('e.g. Buster'), 'Buster');
    await waitFor(() => {
      expect(screen.getByDisplayValue('Buster')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Continue →'));

    await waitFor(() => {
      expect(screen.getByText('Review Booking Request')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('I accept the Tog & Dogs Terms of Service and Privacy Policy.'));
    await waitFor(() => {
      expect(screen.getByText('☑')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('Submit Booking Request'));

    await waitFor(() => {
      expect(screen.getByText('View My Bookings')).toBeTruthy();
    });

    fireEvent.press(screen.getByText('View My Bookings'));
    expect(mockNavigate).toHaveBeenCalledWith('Bookings');
  });
});
