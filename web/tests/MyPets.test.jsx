import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MyPets from '../src/components/MyPets';
import { getSession, getEffectiveRole } from '../src/api/auth';
import { getClientPets } from '../src/api/client';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock auth API
vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  signIn: vi.fn(),
  getEffectiveRole: vi.fn()
}));

// Mock client API
vi.mock('../src/api/client', () => ({
  getClientPets: vi.fn()
}));

// Mock UserProfile component since it contains auth state/UI elements
vi.mock('../src/components/UserProfile', () => ({
  default: () => <div data-testid="user-profile">UserProfileMock</div>
}));

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
      expect(screen.getByText('Network Error')).toBeInTheDocument();
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
      expect(screen.getByText('Network Error')).toBeInTheDocument();
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

  it('8. no create, edit, archive, restore, or delete controls appear', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.com' } } });
    getEffectiveRole.mockReturnValue('client');
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Buddy', species: 'Dog' }]
    });

    render(<MyPets />);

    await waitFor(() => {
      expect(screen.getByText('Buddy')).toBeInTheDocument();
    });

    // Check that there are no buttons matching create, edit, delete, archive, or save
    const buttons = screen.queryAllByRole('button');
    const controlKeywords = [/create/i, /add/i, /edit/i, /delete/i, /archive/i, /restore/i, /save/i];
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
});
