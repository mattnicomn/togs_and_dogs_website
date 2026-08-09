/**
 * Phase 24A-5: My Pets Screen Tests (RNTL v14)
 *
 * Tests read and inline edit behavior for My Pets screen.
 * Verifies client pet updates using PUT /client/pets/{petId}.
 * No pet creation, deletion, archiving, or restoring capability is tested or supported.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { Alert } from 'react-native';

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
const mockUpdateClientPet = jest.fn();
jest.mock('../src/api/client', () => ({
  getClientPets: (...args: any[]) => mockGetClientPets(...args),
  updateClientPet: (...args: any[]) => mockUpdateClientPet(...args),
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

  it('renders Edit Profile action but does not render Delete action', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await waitFor(() => {
      expect(screen.getByText('Edit Profile')).toBeTruthy();
      expect(screen.queryByText('Delete')).toBeNull();
    });
  });
});

describe('MyPetsScreen - Inline Editing (Phase 24A-5)', () => {
  it('enters edit mode and pre-populates form fields with current values', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await waitFor(() => {
      expect(screen.getByText('Edit Profile')).toBeTruthy();
    });

    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));
    await waitFor(() => {
      expect(screen.getByLabelText('Pet Name').props.value).toBe('Buddy');
      expect(screen.getByLabelText('Species').props.value).toBe('Dog');
      expect(screen.getByLabelText('Breed').props.value).toBe('Golden Retriever');
      expect(screen.getByLabelText('Age').props.value).toBe('3 years');
      expect(screen.getByLabelText('Care Instructions').props.value).toBe('Walks twice daily');
      expect(screen.getByLabelText('Feeding Notes').props.value).toBe('Dry food twice daily');
      expect(screen.getByLabelText('Behavior Notes').props.value).toBe('Friendly with other dogs');
      expect(screen.getByLabelText('Vet Name').props.value).toBe('Dr. Smith');
      expect(screen.getByLabelText('Vet Phone').props.value).toBe('555-1234');
    });
  });

  it('does not display unsupported fields like color or weight', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));
    await waitFor(() => {
      expect(screen.queryByLabelText('Color')).toBeNull();
      expect(screen.queryByLabelText('Weight')).toBeNull();
    });
  });

  it('disables Save button when form is pristine', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));
    await waitFor(() => {
      const saveBtn = screen.getByLabelText('Save pet changes');
      expect(saveBtn.props.accessibilityState.disabled).toBe(true);
    });
  });

  it('disables Save button when pet name is blank', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));
    await waitFor(() => {
      expect(screen.getByLabelText('Pet Name')).toBeTruthy();
    });

    await fireEvent.changeText(screen.getByLabelText('Pet Name'), '   ');
    await waitFor(() => {
      const saveBtn = screen.getByLabelText('Save pet changes');
      expect(saveBtn.props.accessibilityState.disabled).toBe(true);
    });
  });

  it('submits updated payload to PUT /client/pets/{petId} on save', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    mockUpdateClientPet.mockResolvedValue({
      ...MOCK_PETS[0],
      breed: 'Golden Retriever Mix',
      care_instructions: 'Walks 3 times daily',
    });

    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));

    await fireEvent.changeText(screen.getByLabelText('Breed'), 'Golden Retriever Mix');
    await fireEvent.changeText(screen.getByLabelText('Care Instructions'), 'Walks 3 times daily');

    const saveBtn = screen.getByLabelText('Save pet changes');
    expect(saveBtn.props.accessibilityState.disabled).toBe(false);

    await fireEvent.press(saveBtn);

    await waitFor(() => {
      expect(mockUpdateClientPet).toHaveBeenCalledTimes(1);
      expect(mockUpdateClientPet).toHaveBeenCalledWith('pet-1', {
        name: 'Buddy',
        species: 'Dog',
        breed: 'Golden Retriever Mix',
        age: '3 years',
        care_instructions: 'Walks 3 times daily',
        feeding_notes: 'Dry food twice daily',
        medication_notes: '',
        behavior_notes: 'Friendly with other dogs',
        health: {
          vet_name: 'Dr. Smith',
          vet_phone: '555-1234',
        },
      });
      expect(screen.getByText('✓ Pet details saved successfully.')).toBeTruthy();
    });
  });

  it('omits immutable and server-owned fields from update payload', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    mockUpdateClientPet.mockResolvedValue(MOCK_PETS[0]);

    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));

    await fireEvent.changeText(screen.getByLabelText('Age'), '4 years');
    await fireEvent.press(screen.getByLabelText('Save pet changes'));

    await waitFor(() => {
      const payload = mockUpdateClientPet.mock.calls[0][1];
      expect(payload.pet_id).toBeUndefined();
      expect(payload.client_id).toBeUndefined();
      expect(payload.company_id).toBeUndefined();
      expect(payload.PK).toBeUndefined();
      expect(payload.SK).toBeUndefined();
      expect(payload.is_active).toBeUndefined();
    });
  });

  it('supports sending optional empty strings to clear field values', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    mockUpdateClientPet.mockResolvedValue({ ...MOCK_PETS[0], breed: '' });

    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));

    await fireEvent.changeText(screen.getByLabelText('Breed'), '');
    await fireEvent.press(screen.getByLabelText('Save pet changes'));

    await waitFor(() => {
      const payload = mockUpdateClientPet.mock.calls[0][1];
      expect(payload.breed).toBe('');
    });
  });

  it('preserves edit mode and shows error message on API failure', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    mockUpdateClientPet.mockRejectedValue(new Error('Failed to update pet on server.'));

    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));

    await fireEvent.changeText(screen.getByLabelText('Age'), '4 years');
    await fireEvent.press(screen.getByLabelText('Save pet changes'));

    await waitFor(() => {
      expect(screen.getByText('⚠️ Failed to update pet on server.')).toBeTruthy();
      expect(screen.getByLabelText('Pet Name').props.value).toBe('Buddy');
    });
  });

  it('restores original values when Cancel is pressed on pristine form', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });

    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));

    await fireEvent.press(screen.getByLabelText('Cancel editing pet details'));

    await waitFor(() => {
      expect(screen.queryByLabelText('Pet Name')).toBeNull();
      expect(screen.getByText('Walks twice daily')).toBeTruthy();
    });
  });

  it('prompts Alert confirmation when Cancel is pressed on dirty form', async () => {
    const alertSpy = jest.spyOn(Alert, 'alert');
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });

    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));

    await fireEvent.changeText(screen.getByLabelText('Age'), '4 years');
    await fireEvent.press(screen.getByLabelText('Cancel editing pet details'));

    expect(alertSpy).toHaveBeenCalledWith(
      'Discard Unsaved Changes?',
      'You have unsaved pet edits. Are you sure you want to discard them?',
      expect.any(Array)
    );
    alertSpy.mockRestore();
  });



  it('invokes logout when update returns session expired error', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });
    mockUpdateClientPet.mockRejectedValue(new Error('Your session expired. Please sign in again.'));

    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));
    await fireEvent.press(screen.getByLabelText('Edit profile for Buddy'));

    await fireEvent.changeText(screen.getByLabelText('Age'), '4 years');
    await fireEvent.press(screen.getByLabelText('Save pet changes'));

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
  });

  it('preserves accessible roles and labels on edit UI components', async () => {
    mockGetClientPets.mockResolvedValue({ pets: MOCK_PETS });

    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
    await fireEvent.press(screen.getByLabelText('View details for Buddy'));

    const editBtn = screen.getByLabelText('Edit profile for Buddy');
    expect(editBtn.props.accessibilityRole).toBe('button');

    await fireEvent.press(editBtn);

    await waitFor(() => {
      const saveBtn = screen.getByLabelText('Save pet changes');
      const cancelBtn = screen.getByLabelText('Cancel editing pet details');
      expect(saveBtn.props.accessibilityRole).toBe('button');
      expect(cancelBtn.props.accessibilityRole).toBe('button');
      expect(screen.getByLabelText('Pet Name')).toBeTruthy();
      expect(screen.getByLabelText('Care Instructions')).toBeTruthy();
    });
  });
});

describe('MyPetsScreen - API Contract', () => {
  it('calls GET /client/pets on initial render', async () => {
    mockGetClientPets.mockResolvedValue({ pets: [] });
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(mockGetClientPets).toHaveBeenCalled();
    });
  });
});

describe('MyPetsScreen - Session Expiration', () => {
  it('invokes logout and suppresses error display on session expiration error', async () => {
    mockGetClientPets.mockRejectedValue(new Error('Your session expired. Please sign in again.'));
    await render(<MyPetsScreen />);
    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
    expect(screen.queryByText(/Your session expired/)).toBeNull();
    expect(screen.queryByText('Retry')).toBeNull();
    expect(mockGetClientPets).toHaveBeenCalledTimes(1);
  });
});
