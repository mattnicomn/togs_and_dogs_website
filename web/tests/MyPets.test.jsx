import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MyPets from '../src/components/MyPets';
import { getSession, getEffectiveRole } from '../src/api/auth';
import { getClientPets, updateClientPet } from '../src/api/client';
import { PET_FIELDS } from '../src/generated/contracts';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock auth API
vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  signIn: vi.fn(),
  getEffectiveRole: vi.fn()
}));

// Mock client API
vi.mock('../src/api/client', () => ({
  getClientPets: vi.fn(),
  updateClientPet: vi.fn()
}));

// Mock UserProfile component since it contains auth state/UI elements
vi.mock('../src/components/UserProfile', () => ({
  default: () => <div data-testid="user-profile">UserProfileMock</div>
}));

let mockBlockerState = { state: 'unblocked', proceed: vi.fn(), reset: vi.fn() };

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useBlocker: vi.fn(() => mockBlockerState)
  };
});

describe('MyPets Component Tests', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('1. unauthenticated state does not fetch pets and renders login', async () => {
    getSession.mockResolvedValue(null);

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Client Login')).toBeInTheDocument();
    });

    expect(getClientPets).not.toHaveBeenCalled();
  });

  it('2. authenticated loading state appears', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    // Keep pet fetch unresolved
    getClientPets.mockReturnValue(new Promise(() => {}));

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Loading your pets...')).toBeInTheDocument();
    });
  });

  it('3. populated response renders expected pet information', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [
        {
          pet_id: 'pet-abc',
          name: 'Buddy',
          species: 'Dog',
          breed: 'Golden Retriever',
          age: '3 years',
          care_instructions: 'Feed twice daily',
          feeding_notes: 'Dry food only',
          medication_notes: 'None',
          behavior_notes: 'Very friendly'
        }
      ]
    });

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Buddy')).toBeInTheDocument();
    });

    expect(screen.getByText(/Golden Retriever/)).toBeInTheDocument();
    expect(screen.getByText(/3 years/)).toBeInTheDocument();
    expect(screen.getByText(/Feed twice daily/)).toBeInTheDocument();
    expect(screen.getByText(/Dry food only/)).toBeInTheDocument();
    expect(screen.getByText(/Very friendly/)).toBeInTheDocument();
  });

  it('4. empty response renders the empty state', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({ pets: [] });

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('No pets on file')).toBeInTheDocument();
      expect(screen.getByText("We don't have any pet records linked to your account yet.")).toBeInTheDocument();
    });
  });

  it('5. API failure renders a safe error state', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockRejectedValue(new Error('Network Error'));

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load pets. Please try again.')).toBeInTheDocument();
    });
  });

  it('6. Retry performs another GET request', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockRejectedValueOnce(new Error('Network Error'));
    getClientPets.mockResolvedValueOnce({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog' }]
    });

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load pets. Please try again.')).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText('Buddy')).toBeInTheDocument();
    });
    expect(getClientPets).toHaveBeenCalledTimes(2);
  });

  it('7. restricted fields are not rendered', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [
        {
          pet_id: 'pet-abc',
          name: 'Buddy',
          species: 'Dog',
          internal_pricing_notes: 'Sensitive pricing info',
          quote_amount: 120,
          meet_and_greet_notes: 'Meet and greet thoughts'
        }
      ]
    });

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Buddy')).toBeInTheDocument();
    });

    expect(screen.queryByText(/Sensitive pricing info/)).not.toBeInTheDocument();
    expect(screen.queryByText(/120/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Meet and greet thoughts/)).not.toBeInTheDocument();
  });

  it('8. no create, archive, restore, or delete controls appear', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog' }]
    });

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Buddy')).toBeInTheDocument();
    });

    // Check that there are no buttons matching create, delete, archive, or restore
    const buttons = screen.queryAllByRole('button');
    const controlKeywords = [/create/i, /add/i, /delete/i, /archive/i, /restore/i];
    buttons.forEach(btn => {
      controlKeywords.forEach(regex => {
        expect(btn.textContent).not.toMatch(regex);
      });
    });
  });

  it('9. no mutation API is called during load or rendering', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog' }]
    });

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Buddy')).toBeInTheDocument();
    });

    expect(getClientPets).toHaveBeenCalledTimes(1);
  });

  it('10. semantic list markup is present', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [
        { pet_id: 'pet-1', name: 'Buddy', species: 'Dog' },
        { pet_id: 'pet-2', name: 'Max', species: 'Dog' }
      ]
    });

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Buddy')).toBeInTheDocument();
    });

    const listElement = screen.getByRole('list');
    expect(listElement.tagName).toBe('UL');

    const listItems = screen.getAllByRole('listitem');
    expect(listItems.length).toBe(2);
    expect(listItems[0].tagName).toBe('LI');
  });

  it('11. loading/error status uses the expected live-region behavior', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({ pets: [] });

    const { container } = render(<MyPets />);

    await screen.findByText('No pets on file');

    // The wrapper of the loading/error/empty elements has aria-live="polite"
    const liveRegion = container.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
  });

  it('12. unlinked client-role identity renders client support message', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({ pets: [], message: 'No local profile linked', linked_profile: false });

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Your portal account is not yet linked to a client profile. Please contact support.')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });

  it('13. unlinked owner/admin-role identity renders administrative warning and redirect link', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'admin@usmissionhero.com' } } });
    getEffectiveRole.mockReturnValue('admin');
    getClientPets.mockResolvedValue({ pets: [], message: 'No local profile linked', linked_profile: false });

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('You are signed in as an administrator. My Pets is for linked client accounts. Use Client Management to view and manage client pets.')).toBeInTheDocument();
    });

    const link = screen.getByRole('link', { name: /go to admin dashboard/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/admin');
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });

  it('14. transient API failure shows safe generic message and retry, never raw internals', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockRejectedValue(new Error('Missing petId in path'));

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load pets. Please try again.')).toBeInTheDocument();
    });

    expect(screen.queryByText('Missing petId in path')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('15. clicking Edit Pet toggles the inline editor form', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog', breed: 'Retriever' }]
    });

    render(<MyPets />);

    await screen.findByText('Buddy');

    const editBtn = screen.getByRole('button', { name: /edit pet/i });
    fireEvent.click(editBtn);

    // Form inputs should be visible
    expect(screen.getByText('Edit Pet Details')).toBeInTheDocument();
    const nameInput = screen.getByLabelText(/^name/i);
    expect(nameInput.value).toBe('Buddy');
    
    const speciesInput = screen.getByLabelText(/species/i);
    expect(speciesInput.value).toBe('Dog');

    const breedInput = screen.getByLabelText(/breed/i);
    expect(breedInput.value).toBe('Retriever');

    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('16. clicking Cancel exits the inline editor form', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog' }]
    });

    render(<MyPets />);

    await screen.findByText('Buddy');

    fireEvent.click(screen.getByRole('button', { name: /edit pet/i }));
    expect(screen.getByText('Edit Pet Details')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(screen.queryByText('Edit Pet Details')).not.toBeInTheDocument();
    expect(screen.getByText('Buddy')).toBeInTheDocument();
  });

  it('17. saving updates the pet and shows success toast', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [{
        pet_id: 'pet-1',
        name: 'Buddy',
        species: 'Dog',
        breed: 'Golden Retriever',
        age: '3 years',
        care_instructions: 'Use the back-door leash.',
        feeding_notes: 'One cup twice daily.',
        medication_notes: '',
        behavior_notes: 'Friendly with familiar dogs.',
        health: {
          vet_name: 'Northside Vet',
          vet_phone: '555-0100'
        },
        internal_pricing_notes: 'staff-only fixture value',
        quote_amount: 125,
        is_active: true
      }]
    });
    updateClientPet.mockResolvedValue({
      pet_id: 'pet-1',
      name: 'Buddy Jr.',
      species: 'Dog',
      is_active: true
    });

    render(<MyPets />);

    await screen.findByText('Buddy');

    fireEvent.click(screen.getByRole('button', { name: /edit pet/i }));

    const nameInput = screen.getByLabelText(/^name/i);
    fireEvent.change(nameInput, { target: { value: 'Buddy Jr.' } });

    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(updateClientPet).toHaveBeenCalledTimes(1);
      expect(updateClientPet).toHaveBeenCalledWith('pet-1', {
        name: 'Buddy Jr.',
        species: 'Dog',
        breed: 'Golden Retriever',
        age: '3 years',
        care_instructions: 'Use the back-door leash.',
        feeding_notes: 'One cup twice daily.',
        medication_notes: '',
        behavior_notes: 'Friendly with familiar dogs.',
        health: {
          vet_name: 'Northside Vet',
          vet_phone: '555-0100'
        }
      });
      expect(screen.getByText('Pet "Buddy Jr." updated successfully.')).toBeInTheDocument();
    });
  });

  it('18. save error shows error toast', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog' }]
    });
    updateClientPet.mockRejectedValue(new Error('Validation error'));

    render(<MyPets />);

    await screen.findByText('Buddy');

    fireEvent.click(screen.getByRole('button', { name: /edit pet/i }));
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText('Validation error')).toBeInTheDocument();
    });
  });

  it('19. duplicate pet name triggers warning dialog', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [
        { pet_id: 'pet-1', name: 'Buddy', species: 'Dog' },
        { pet_id: 'pet-2', name: 'Max', species: 'Dog' }
      ]
    });
    updateClientPet.mockResolvedValue({
      pet_id: 'pet-1',
      name: 'Max',
      species: 'Dog',
      is_active: true
    });

    const confirmSpy = vi.spyOn(window, 'confirm');
    confirmSpy.mockReturnValue(true); // User says yes to duplicate warning

    render(<MyPets />);

    await screen.findByText('Buddy');

    fireEvent.click(screen.getAllByRole('button', { name: /edit pet/i })[0]); // Edit Buddy

    const nameInput = screen.getByLabelText(/^name/i);
    fireEvent.change(nameInput, { target: { value: 'Max' } });

    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('already have another pet named "Max"'));
      expect(updateClientPet).toHaveBeenCalled();
    });

    confirmSpy.mockRestore();
  });

  it('20. unsaved Cancel warning appears only when dirty', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog' }]
    });

    const confirmSpy = vi.spyOn(window, 'confirm');

    render(<MyPets />);
    await screen.findByText('Buddy');

    fireEvent.click(screen.getByRole('button', { name: /edit pet/i }));

    // Click cancel when clean - no confirm dialog
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(confirmSpy).not.toHaveBeenCalled();

    // Re-open editor
    fireEvent.click(screen.getByRole('button', { name: /edit pet/i }));

    // Make dirty
    const nameInput = screen.getByLabelText(/^name/i);
    fireEvent.change(nameInput, { target: { value: 'Buddy Changed' } });

    // Cancel when dirty - confirm dialog shown and user chooses Stay (Cancel)
    confirmSpy.mockReturnValue(false); // User clicks "Stay" / "Cancel" on dialog
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(screen.getByLabelText(/^name/i)).toBeInTheDocument(); // Editor still visible

    // Cancel when dirty - confirm dialog shown and user chooses Discard (OK)
    confirmSpy.mockReturnValue(true); // User clicks "Discard" / "OK"
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByLabelText(/^name/i)).not.toBeInTheDocument(); // Editor closed
    });

    confirmSpy.mockRestore();
  });

  it('21. switching pets warns when dirty', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [
        { pet_id: 'pet-1', name: 'Buddy', species: 'Dog' },
        { pet_id: 'pet-2', name: 'Max', species: 'Dog' }
      ]
    });

    const confirmSpy = vi.spyOn(window, 'confirm');
    confirmSpy.mockReturnValue(false); // User stays on Buddy

    render(<MyPets />);
    await screen.findByText('Buddy');
    await screen.findByText('Max');

    // Edit Buddy
    fireEvent.click(screen.getAllByRole('button', { name: /edit pet/i })[0]);
    const nameInput = screen.getByLabelText(/^name/i);
    fireEvent.change(nameInput, { target: { value: 'Buddy Changed' } });

    // Try editing Max (it is the only "Edit Pet" button visible since Buddy is in edit mode)
    fireEvent.click(screen.getByRole('button', { name: /edit pet/i }));
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('unsaved pet changes'));
    
    confirmSpy.mockRestore();
  });

  it('22. beforeunload protection registered only while dirty', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog' }]
    });

    const addEventListenerSpy = vi.spyOn(window, 'addEventListener');
    const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

    render(<MyPets />);
    await screen.findByText('Buddy');

    // Start edit - clean
    fireEvent.click(screen.getByRole('button', { name: /edit pet/i }));

    // Make dirty
    const nameInput = screen.getByLabelText(/^name/i);
    fireEvent.change(nameInput, { target: { value: 'Buddy Changed' } });

    // Expect beforeunload listener registered
    expect(addEventListenerSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function));

    // Save pet (clean state)
    updateClientPet.mockResolvedValue({ pet_id: 'pet-1', name: 'Buddy Changed', species: 'Dog' });
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy Changed', species: 'Dog', is_active: true }]
    });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      // Expect beforeunload listener removed
      expect(removeEventListenerSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function));
    });

    addEventListenerSpy.mockRestore();
    removeEventListenerSpy.mockRestore();
  });

  it('23. reload failure displays warning and Retry Reload button, successful retry closes editor', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    // First call (mount) succeeds
    getClientPets.mockResolvedValueOnce({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog' }]
    });
    updateClientPet.mockResolvedValue({ pet_id: 'pet-1', name: 'Buddy Saved', species: 'Dog' });
    // Second call (reload) fails
    getClientPets.mockRejectedValueOnce(new Error('Network error during reload'));

    render(<MyPets />);
    await screen.findByText('Buddy');

    fireEvent.click(screen.getByRole('button', { name: /edit pet/i }));
    const nameInput = screen.getByLabelText(/^name/i);
    fireEvent.change(nameInput, { target: { value: 'Buddy Saved' } });

    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    // Reload failure warning shown, editor stays visible
    await screen.findByText(/could not be reloaded/i);
    const retryBtn = screen.getByRole('button', { name: /retry reload/i });
    expect(retryBtn).toBeInTheDocument();
    expect(screen.getByLabelText(/^name/i)).toBeInTheDocument(); // Editor still open

    // Mock subsequent reload success
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy Saved', species: 'Dog', is_active: true }]
    });

    // Click retry
    fireEvent.click(retryBtn);

    // Editor closes and success notification shown
    await waitFor(() => {
      expect(screen.queryByLabelText(/^name/i)).not.toBeInTheDocument();
      expect(screen.getByText('Pet "Buddy Saved" updated successfully.')).toBeInTheDocument();
    });
  });

  it('24. applies PET_FIELDS.fieldLimits maxLength attributes to top-level customer pet inputs while leaving nested health fields unconstrained', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog', breed: 'Golden', age: '3' }]
    });

    render(<MyPets />);
    await screen.findByText('Buddy');

    fireEvent.click(screen.getByRole('button', { name: /edit pet/i }));

    const nameInput = screen.getByLabelText(/name \*/i);
    const speciesInput = screen.getByLabelText(/species/i);
    const breedInput = screen.getByLabelText(/breed/i);
    const ageInput = screen.getByLabelText(/age/i);
    const careInstructionsInput = screen.getByLabelText(/care instructions/i);
    const feedingNotesInput = screen.getByLabelText(/feeding notes/i);
    const medicationNotesInput = screen.getByLabelText(/medication notes/i);
    const behaviorNotesInput = screen.getByLabelText(/behavior notes/i);

    const vetNameInput = screen.getByLabelText(/vet name/i);
    const vetPhoneInput = screen.getByLabelText(/vet phone/i);

    expect(nameInput).toHaveAttribute('maxLength', String(PET_FIELDS.fieldLimits.name));
    expect(speciesInput).toHaveAttribute('maxLength', String(PET_FIELDS.fieldLimits.species));
    expect(breedInput).toHaveAttribute('maxLength', String(PET_FIELDS.fieldLimits.breed));
    expect(ageInput).toHaveAttribute('maxLength', String(PET_FIELDS.fieldLimits.age));
    expect(ageInput).toHaveAttribute('type', 'text');
    expect(careInstructionsInput).toHaveAttribute('maxLength', String(PET_FIELDS.fieldLimits.care_instructions));
    expect(feedingNotesInput).toHaveAttribute('maxLength', String(PET_FIELDS.fieldLimits.feeding_notes));
    expect(medicationNotesInput).toHaveAttribute('maxLength', String(PET_FIELDS.fieldLimits.medication_notes));
    expect(behaviorNotesInput).toHaveAttribute('maxLength', String(PET_FIELDS.fieldLimits.behavior_notes));

    // Confirm nested health fields do not have a contract-driven maxLength attribute
    expect(vetNameInput).not.toHaveAttribute('maxLength');
    expect(vetPhoneInput).not.toHaveAttribute('maxLength');
  });
});
