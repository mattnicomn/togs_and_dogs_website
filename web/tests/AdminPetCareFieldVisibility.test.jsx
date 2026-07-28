import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import ClientDetailDrawer from '../src/components/ClientDetailDrawer';

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

const sampleClient = {
  client_id: 'client-test-1',
  display_name: 'Test Client',
  email: 'client@example.com',
  phone: '555-0100',
  address: '100 Main St',
  is_active: true,
};

const samplePetWithCareInfo = {
  pet_id: 'pet-123456abcdef',
  client_id: 'client-test-1',
  name: 'TestPet_ScenarioB',
  species: 'POM',
  breed: 'Pomeranian',
  age: '56',
  care_instructions: 'test care instructions',
  feeding_notes: 'test feeding notes',
  medication_notes: 'stest medication notes',
  behavior_notes: 'test behavior notes',
  color: 'Fluffy White',
  weight: '12',
  vet_name: 'Dr. Smith',
  vet_phone: '555-1234',
  vet_notes: 'Staff vet note that should not be touched',
  is_active: true,
};

const sampleDuplicatePet1 = {
  pet_id: 'pet-aaaaaa111111',
  client_id: 'client-test-1',
  name: 'TestPet_ScenarioB',
  species: 'POM',
  breed: '',
  age: '56',
  care_instructions: 'test care instructions 1',
  feeding_notes: 'test feeding notes 1',
  medication_notes: 'stest 1',
  is_active: true,
};

const sampleDuplicatePet2 = {
  pet_id: 'pet-bbbbbb222222',
  client_id: 'client-test-1',
  name: 'TestPet_ScenarioB',
  species: 'POM',
  breed: '',
  age: '2',
  care_instructions: 'test care instructions 2',
  feeding_notes: 'test feeding notes 2',
  medication_notes: 'stest 2',
  is_active: true,
};

const sampleEmptyPet = {
  pet_id: 'pet-empty-999',
  client_id: 'client-test-1',
  name: 'EmptyPet',
  species: '',
  breed: '',
  age: '',
  care_instructions: '',
  feeding_notes: '',
  medication_notes: '',
  behavior_notes: '',
  is_active: true,
};

describe('Phase 1B.5C-A.1 — Admin Pet Care Field Visibility Hotfix', () => {
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
      pets: [samplePetWithCareInfo],
      loadingPets: false,
      onExecuteAction: vi.fn(),
      onLinkEmail: vi.fn(),
      onCreateProfile: vi.fn(),
      isProtectedProfile: vi.fn(() => false),
      clientLinkPrompt: null,
      setClientLinkPrompt: vi.fn(),
      onLinkExistingClientOnboard: vi.fn(),
      onPetCreate: vi.fn().mockResolvedValue({ ...samplePetWithCareInfo, pet_id: 'pet-new' }),
      onPetUpdate: vi.fn().mockResolvedValue({ ...samplePetWithCareInfo, age: '57' }),
      userRole: 'staff',
    };
  });

  it('1. read-only drawer renders age, care_instructions, and feeding_notes', () => {
    render(<ClientDetailDrawer {...defaultProps} />);

    // Open View for pet
    fireEvent.click(screen.getByRole('button', { name: /View/i }));

    expect(screen.getByText('56')).toBeInTheDocument();
    expect(screen.getByText('test care instructions')).toBeInTheDocument();
    expect(screen.getByText('test feeding notes')).toBeInTheDocument();
  });

  it('2. empty values display established empty-state presentation (—)', () => {
    const props = {
      ...defaultProps,
      pets: [sampleEmptyPet],
    };
    render(<ClientDetailDrawer {...props} />);

    fireEvent.click(screen.getByRole('button', { name: /View/i }));

    // Verify empty fields render dash
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThan(0);
  });

  it('3. edit mode renders input/textarea fields for age, care_instructions, and feeding_notes', () => {
    render(<ClientDetailDrawer {...defaultProps} />);

    fireEvent.click(screen.getByRole('button', { name: /View/i }));
    fireEvent.click(screen.getByRole('button', { name: /Edit Pet/i }));

    expect(screen.getByLabelText(/Age/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Care Instructions/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Feeding Notes/i)).toBeInTheDocument();
  });

  it('4. save payload includes age, care_instructions, and feeding_notes with correct API names', async () => {
    render(<ClientDetailDrawer {...defaultProps} />);

    fireEvent.click(screen.getByRole('button', { name: /View/i }));
    fireEvent.click(screen.getByRole('button', { name: /Edit Pet/i }));

    fireEvent.change(screen.getByLabelText(/Age/i), { target: { value: '57' } });
    fireEvent.change(screen.getByLabelText(/Care Instructions/i), { target: { value: 'updated care' } });
    fireEvent.change(screen.getByLabelText(/Feeding Notes/i), { target: { value: 'updated feeding' } });

    fireEvent.click(screen.getByRole('button', { name: /Save Pet/i }));

    await waitFor(() => {
      expect(defaultProps.onPetUpdate).toHaveBeenCalledWith(
        'pet-123456abcdef',
        'client-test-1',
        expect.objectContaining({
          name: 'TestPet_ScenarioB',
          age: '57',
          care_instructions: 'updated care',
          feeding_notes: 'updated feeding',
          medication_notes: 'stest medication notes',
          behavior_notes: 'test behavior notes',
        }),
        'update'
      );
    });
  });

  it('5. save payload excludes color, weight, vet_notes, and internal identifiers', async () => {
    render(<ClientDetailDrawer {...defaultProps} />);

    fireEvent.click(screen.getByRole('button', { name: /View/i }));
    fireEvent.click(screen.getByRole('button', { name: /Edit Pet/i }));

    fireEvent.click(screen.getByRole('button', { name: /Save Pet/i }));

    await waitFor(() => {
      const payload = defaultProps.onPetUpdate.mock.calls[0][2];
      expect(payload).not.toHaveProperty('color');
      expect(payload).not.toHaveProperty('weight');
      expect(payload).not.toHaveProperty('vet_notes');
      expect(payload).not.toHaveProperty('pet_id');
      expect(payload).not.toHaveProperty('client_id');
      expect(payload).not.toHaveProperty('company_id');
      expect(payload).not.toHaveProperty('PK');
      expect(payload).not.toHaveProperty('SK');
    });
  });

  it('6. medication_notes continues to use established compatibility mapping without affecting vet_notes', async () => {
    render(<ClientDetailDrawer {...defaultProps} />);

    fireEvent.click(screen.getByRole('button', { name: /View/i }));
    expect(screen.getByText('stest medication notes')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Edit Pet/i }));
    fireEvent.change(screen.getByLabelText(/Medical Notes/i), { target: { value: 'updated medical notes' } });

    fireEvent.click(screen.getByRole('button', { name: /Save Pet/i }));

    await waitFor(() => {
      const payload = defaultProps.onPetUpdate.mock.calls[0][2];
      expect(payload.medication_notes).toBe('updated medical notes');
      expect(payload).not.toHaveProperty('vet_notes');
    });
  });

  it('7. duplicate-name pets are keyed and selected by pet_id and visually distinguishable using abbreviated IDs', () => {
    const props = {
      ...defaultProps,
      pets: [sampleDuplicatePet1, sampleDuplicatePet2],
    };
    render(<ClientDetailDrawer {...props} />);

    // Abbreviated IDs are displayed in the list
    expect(screen.getByText(/ID: …111111/i)).toBeInTheDocument();
    expect(screen.getByText(/ID: …222222/i)).toBeInTheDocument();

    // Clicking View on the second duplicate pet opens that specific pet by pet_id
    const viewButtons = screen.getAllByRole('button', { name: /View/i });
    fireEvent.click(viewButtons[1]); // Click second duplicate pet (sampleDuplicatePet2)

    expect(screen.getByText('test care instructions 2')).toBeInTheDocument();
    expect(screen.getByText('test feeding notes 2')).toBeInTheDocument();
  });

  it('8. existing archive/restore and unsaved-change behavior remains intact', async () => {
    render(<ClientDetailDrawer {...defaultProps} />);

    // Unsaved changes confirm dialog on cancel
    fireEvent.click(screen.getByRole('button', { name: /View/i }));
    fireEvent.click(screen.getByRole('button', { name: /Edit Pet/i }));

    fireEvent.change(screen.getByLabelText(/Age/i), { target: { value: '99' } });

    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringMatching(/unsaved pet changes/i));

    // Archive behavior
    confirmSpy.mockImplementation(() => true);
    fireEvent.click(screen.getByRole('button', { name: /Archive/i }));

    await waitFor(() => {
      expect(defaultProps.onPetUpdate).toHaveBeenCalledWith(
        'pet-123456abcdef',
        'client-test-1',
        { is_active: false },
        'archive'
      );
    });
  });
});
