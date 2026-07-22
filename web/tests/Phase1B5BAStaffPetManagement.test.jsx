import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import ClientDetailDrawer from '../src/components/ClientDetailDrawer';

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

const sampleClient = {
  client_id: 'client-jane',
  display_name: 'Jane Doe',
  email: 'jane@example.com',
  phone: '555-0199',
  address: '123 Main St',
  is_active: true,
};

const sampleActivePet = {
  pet_id: 'pet-1',
  client_id: 'client-jane',
  name: 'Buddy',
  species: 'DOG',
  breed: 'Golden Retriever',
  color: 'Golden',
  weight: '65',
  medical_notes: 'None',
  behavioral_notes: 'Friendly',
  vet_name: 'Dr. Smith',
  vet_phone: '555-1111',
  is_active: true,
};

const sampleArchivedPet = {
  pet_id: 'pet-2',
  client_id: 'client-jane',
  name: 'Max',
  species: 'CAT',
  breed: 'Siamese',
  color: 'White/Brown',
  weight: '10',
  medical_notes: 'Asthma',
  behavioral_notes: 'Shy',
  vet_name: 'Dr. Jones',
  vet_phone: '555-2222',
  is_active: false,
};

describe('Phase 1B.5B-A Staff Pet Management - ClientDetailDrawer Subview', () => {
  let defaultProps;

  beforeEach(() => {
    vi.clearAllMocks();
    defaultProps = {
      client: sampleClient,
      mode: 'view',
      formValues: sampleClient,
      setFormValues: vi.fn(),
      onClose: vi.fn(),
      onEdit: vi.fn(),
      onCancel: vi.fn(),
      onSave: vi.fn(),
      isSaving: false,
      pets: [sampleActivePet, sampleArchivedPet],
      loadingPets: false,
      onExecuteAction: vi.fn(),
      onLinkEmail: vi.fn(),
      onCreateProfile: vi.fn(),
      isProtectedProfile: vi.fn(() => false),
      clientLinkPrompt: null,
      setClientLinkPrompt: vi.fn(),
      onLinkExistingClientOnboard: vi.fn(),
      onPetCreate: vi.fn().mockResolvedValue({ ...sampleActivePet, pet_id: 'pet-new', name: 'Luna' }),
      onPetUpdate: vi.fn().mockResolvedValue({ ...sampleActivePet, name: 'Buddy Updated' }),
      userRole: 'staff',
    };
  });

  it('1. renders pet list with "+ Add Pet" button and displays active and archived badges', () => {
    render(<ClientDetailDrawer {...defaultProps} />);
    
    expect(screen.getByText('Pets')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /\+ Add Pet/i })).toBeInTheDocument();
    expect(screen.getByText('Buddy')).toBeInTheDocument();
    expect(screen.getByText('Max')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Archived')).toBeInTheDocument();
  });

  it('2. clicking "+ Add Pet" opens same drawer subview with Back to Client button and focuses name field', () => {
    render(<ClientDetailDrawer {...defaultProps} />);
    
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Pet/i }));
    
    expect(screen.getByRole('button', { name: /Back to client/i })).toBeInTheDocument();
    const nameInput = screen.getByLabelText(/Name \*/i);
    expect(nameInput).toBeInTheDocument();
    expect(document.activeElement).toBe(nameInput);
  });

  it('3. submitting valid new pet calls onPetCreate with trusted client_id', async () => {
    render(<ClientDetailDrawer {...defaultProps} />);
    
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Pet/i }));
    
    fireEvent.change(screen.getByLabelText(/Name \*/i), { target: { value: 'Luna' } });
    fireEvent.change(screen.getByLabelText(/Breed/i), { target: { value: 'Poodle' } });
    
    fireEvent.click(screen.getByRole('button', { name: /Save Pet/i }));
    
    await waitFor(() => {
      expect(defaultProps.onPetCreate).toHaveBeenCalledWith('client-jane', expect.objectContaining({
        name: 'Luna',
        breed: 'Poodle'
      }));
    });
  });

  it('4. selecting View on a pet opens detail subview with pre-populated fields', () => {
    render(<ClientDetailDrawer {...defaultProps} />);
    
    const viewButtons = screen.getAllByRole('button', { name: /View/i });
    fireEvent.click(viewButtons[0]); // Click View for Buddy
    
    expect(screen.getByRole('button', { name: /Back to client/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Edit Pet/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Archive/i })).toBeInTheDocument();
    expect(screen.getAllByText('Buddy').length).toBeGreaterThan(0);
    expect(screen.getByText('Golden Retriever')).toBeInTheDocument();
  });

  it('5. editing pet pre-populates form and submitting calls onPetUpdate with correct parameters', async () => {
    render(<ClientDetailDrawer {...defaultProps} />);
    
    // Open View for Buddy
    fireEvent.click(screen.getAllByRole('button', { name: /View/i })[0]);
    // Click Edit Pet
    fireEvent.click(screen.getByRole('button', { name: /Edit Pet/i }));
    
    const nameInput = screen.getByLabelText(/^Name/i);
    fireEvent.change(nameInput, { target: { value: 'Buddy Changed' } });
    
    fireEvent.click(screen.getByRole('button', { name: /Save Pet/i }));
    
    await waitFor(() => {
      expect(defaultProps.onPetUpdate).toHaveBeenCalledWith('pet-1', 'client-jane', expect.objectContaining({
        name: 'Buddy Changed'
      }));
    });
  });

  it('6. archiving pet triggers confirm dialog and calls onPetUpdate with is_active: false', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ClientDetailDrawer {...defaultProps} />);
    
    // Open View for Buddy
    fireEvent.click(screen.getAllByRole('button', { name: /View/i })[0]);
    fireEvent.click(screen.getByRole('button', { name: /Archive/i }));
    
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('Archive Buddy?'));
    await waitFor(() => {
      expect(defaultProps.onPetUpdate).toHaveBeenCalledWith('pet-1', 'client-jane', { is_active: false });
    });
    confirmSpy.mockRestore();
  });

  it('7. restoring an archived pet calls onPetUpdate with is_active: true', async () => {
    render(<ClientDetailDrawer {...defaultProps} />);
    
    // Open View for Max (archived)
    fireEvent.click(screen.getAllByRole('button', { name: /View/i })[1]);
    expect(screen.getByText(/This pet is archived/i)).toBeInTheDocument();
    
    fireEvent.click(screen.getByRole('button', { name: /Restore/i }));
    
    await waitFor(() => {
      expect(defaultProps.onPetUpdate).toHaveBeenCalledWith('pet-2', 'client-jane', { is_active: true });
    });
  });

  it('8. duplicate pet name triggers warning banner and allows confirmation via Save Anyway', async () => {
    render(<ClientDetailDrawer {...defaultProps} />);
    
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Pet/i }));
    // Try adding a pet named 'buddy' (existing active pet name)
    fireEvent.change(screen.getByLabelText(/^Name/i), { target: { value: 'buddy ' } });
    
    fireEvent.click(screen.getByRole('button', { name: /Save Pet/i }));
    
    // Should display warning and not call onPetCreate yet
    expect(screen.getByText(/A pet named "Buddy" already exists/i)).toBeInTheDocument();
    expect(defaultProps.onPetCreate).not.toHaveBeenCalled();
    
    // Click Save Anyway
    fireEvent.click(screen.getByRole('button', { name: /Save Anyway/i }));
    
    await waitFor(() => {
      expect(defaultProps.onPetCreate).toHaveBeenCalledWith('client-jane', expect.objectContaining({ name: 'buddy ' }));
    });
  });

  it('9. editing an existing pet does not trigger a duplicate warning for its own name', async () => {
    render(<ClientDetailDrawer {...defaultProps} />);
    
    fireEvent.click(screen.getAllByRole('button', { name: /View/i })[0]); // Buddy
    fireEvent.click(screen.getByRole('button', { name: /Edit Pet/i }));
    
    // Keep name as 'Buddy' and edit breed
    fireEvent.change(screen.getByLabelText(/Breed/i), { target: { value: 'Golden Mix' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Pet/i }));
    
    await waitFor(() => {
      expect(defaultProps.onPetUpdate).toHaveBeenCalled();
    });
    expect(screen.queryByText(/already exists/i)).not.toBeInTheDocument();
  });

  it('10. dirty pet form prompts on Back to Client and discards on confirm', () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ClientDetailDrawer {...defaultProps} />);
    
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Pet/i }));
    fireEvent.change(screen.getByLabelText(/^Name/i), { target: { value: 'Dirty Pet Name' } });
    
    fireEvent.click(screen.getByRole('button', { name: /Back to client/i }));
    
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('unsaved pet changes'));
    // Successfully returns to client view
    expect(screen.getByText('Pets')).toBeInTheDocument();
    confirmSpy.mockRestore();
  });

  it('11. pressing Escape while in pet subview goes back to client view', () => {
    render(<ClientDetailDrawer {...defaultProps} />);
    
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Pet/i }));
    expect(screen.getByRole('button', { name: /Back to client/i })).toBeInTheDocument();
    
    act(() => {
      fireEvent.keyDown(document, { key: 'Escape' });
    });
    
    // Returned to client view
    expect(screen.getByText('Client Overview')).toBeInTheDocument();
  });
});
