/**
 * Phase 24A-4: My Pets Screen Tests (RNTL v14)
 *
 * Tests read-only My Pets list and detail behavior.
 * No editing, creating, or deleting capability is tested or expected.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';

// Mock auth
const mockLogout = jest.fn();
jest.mock('../src/auth/useAuth', () => ({
  useAuth: () => ({
    login: jest.fn(),
    logout: mockLogout,
    user: 'client@example.com',
    role: 'client',
    isAuthenticated: true,
    isLoading: false,
  }),
}));

// Mock API
const mockGetClientPets = jest.fn();
jest.mock('../src/api/client', () => ({
  getClientPets: (...args: any[]) => mockGetClientPets(...args),
}));

import { MyPetsScreen } from '../src/screens/MyPetsScreen';

beforeEach(() => {
  jest.clearAllMocks();
});


const MOCK_PETS = [
  {
    pet_id: 'pet-1',
    name: 'Buddy',
    species: 'Dog',
    breed: 'Golden Retriever',
    age: '3 years',
    care_instructions: 'Walks twice daily',
    feeding_notes: 'Dry food twice daily',
    medication_notes: '',
    behavior_notes: 'Friendly with other dogs',
    is_active: true,
    health: { vet_name: 'Dr. Smith', vet_phone: '555-1234' },
  },
  {
    pet_id: 'pet-2',
    name: 'Whiskers',
    species: 'Cat',
    breed: 'Tabby',
    age: '5 years',
    is_active: true,
  },
];

describe('MyPetsScreen - List', () => {
  it('shows empty state when no pets exist', async () => {
    mockGetClientPets.mockResolvedValue({ pets: [] });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText('No Pets Yet')).toBeTruthy();
    });
  });

  it('renders pet cards when data exists', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
      expect(screen.getByText(/Whiskers/)).toBeTruthy();
    });
  });

  it('displays species badge', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText('Dog')).toBeTruthy();
      expect(screen.getByText('Cat')).toBeTruthy();
    });
  });

  it('handles missing optional fields gracefully', async () => {
    mockGetClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-3', name: 'NoBreed', is_active: true }],
    });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/NoBreed/)).toBeTruthy();
    });
  });

  it('shows error state on API failure', async () => {
    mockGetClientPets.mockRejectedValue(new Error('Network error'));
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeTruthy();
      expect(screen.getByText('Retry')).toBeTruthy();
    });
  });

  it('shows header title', async () => {
    mockGetClientPets.mockResolvedValue({ pets: [] });
    await render(<MyPetsScreen />);
    expect(screen.getByText('My Pets')).toBeTruthy();
  });
});

describe('MyPetsScreen - Detail', () => {
  it('navigates to pet detail on card press', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await waitFor(() => {
      expect(screen.getByText('Care Instructions')).toBeTruthy();
      expect(screen.getByText('Walks twice daily')).toBeTruthy();
    });
  });

  it('displays health information when present', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await waitFor(() => {
      expect(screen.getByText('Vet Name')).toBeTruthy();
      expect(screen.getByText('Dr. Smith')).toBeTruthy();
    });
  });

  it('omits empty fields in detail view', async () => {
    mockGetClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-empty', name: 'MinimalPet', is_active: true }],
    });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/MinimalPet/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for MinimalPet'));
    await waitFor(() => {
      expect(screen.getByText('No additional details available for this pet.')).toBeTruthy();
    });
  });

  it('has back navigation from detail', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await waitFor(() => {
      expect(screen.getByText('← Back to My Pets')).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('Back to pet list'));
    await waitFor(() => {
      expect(screen.getByText('My Pets')).toBeTruthy();
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
  });

  it('does not render Edit or Delete actions', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await waitFor(() => {
      expect(screen.queryByText('Edit')).toBeNull();
      expect(screen.queryByText('Delete')).toBeNull();
      expect(screen.queryByText('Save')).toBeNull();
    });
  });
});

describe('MyPetsScreen - API Contract', () => {
  it('calls GET /client/pets', async () => {
    mockGetClientPets.mockResolvedValue({ pets: [] });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(mockGetClientPets).toHaveBeenCalled();
    });
  });

  it('does not call any update or delete endpoint', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    // Navigate to detail
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    // Only getClientPets should have been called
    expect(mockGetClientPets).toHaveBeenCalledTimes(1);
  });
});

describe('MyPetsScreen - Session Expiration', () => {
  it('invokes logout and suppresses error display on session expiration error', async () => {
    mockGetClientPets.mockRejectedValue(new Error('Your session expired. Please sign in again.'));
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
    // Verifies raw backend errors, tokens, and retry UI are suppressed during logout
    expect(screen.queryByText(/Your session expired/)).toBeNull();
    expect(screen.queryByText('Retry')).toBeNull();
    expect(mockGetClientPets).toHaveBeenCalledTimes(1);
  });
});

