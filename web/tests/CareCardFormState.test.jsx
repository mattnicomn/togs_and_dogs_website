import React from 'react';
import { fireEvent, render, screen, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CareCard from '../src/components/CareCard';

// Mock the payment API so no real AWS/Stripe/Cognito/Google calls occur.
vi.mock('../src/api/client', () => ({
  createPaymentSession: vi.fn(),
  sendPaymentEmail: vi.fn(),
}));

// A single-pet request record. care_instructions is an easy formData probe:
// it renders activePet.care_instructions when NOT editing and binds to
// formData.care_instructions when editing.
const makePet = ({
  requestId = 'request-1',
  petId = 'pet-a',
  name = 'Alpha',
  care = 'Alpha care notes',
  pets,
} = {}) => {
  const base = {
    pet_id: petId,
    client_id: 'client-1',
    name,
    species: 'DOG',
    breed: 'Lab',
    age: 3,
    care_instructions: care,
    status: 'APPROVED',
    _originItem: {
      PK: `REQ#${requestId}`,
      request_id: requestId,
      client_id: 'client-1',
      linked_client_profile_id: 'client-1',
      status: 'APPROVED',
    },
  };
  if (pets) base._allPets = pets;
  return base;
};

const makeProps = (pet, overrides = {}) => ({
  pet,
  onClose: vi.fn(),
  onUpdate: vi.fn().mockResolvedValue(undefined),
  onStatusUpdate: vi.fn().mockResolvedValue(undefined),
  onPaymentSessionCreated: vi.fn().mockResolvedValue(undefined),
  userRole: 'owner',
  ...overrides,
});

const renderCard = (props) => {
  let utils;
  act(() => {
    utils = render(<CareCard {...props} />);
  });
  return utils;
};

const enterEdit = () => {
  act(() => { fireEvent.click(screen.getByRole('button', { name: /Edit Record/i })); });
};
const clickSave = () => {
  act(() => { fireEvent.click(screen.getByRole('button', { name: /Save Changes/i })); });
};
const clickCancel = () => {
  act(() => { fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i })); });
};

const chipFor = (name) =>
  Array.from(document.querySelectorAll('.pet-chip')).find(
    (c) => c.textContent.replace(/⊘/g, '').trim() === name
  );
const activeChipName = () => {
  const active = Array.from(document.querySelectorAll('.pet-chip')).find((c) => c.className.includes('active'));
  return active ? active.textContent.replace(/⊘/g, '').trim() : null;
};

describe('CareCard form-state & unsaved-edit protection (Gate C3b.2l Batch 4B-3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. opening CareCard initializes form values from the pet', () => {
    renderCard(makeProps(makePet({ name: 'Alpha' })));
    enterEdit();
    expect(screen.getByDisplayValue('Alpha')).toBeInTheDocument();
  });

  it('2. switching pet tabs (not editing) loads the newly selected pet values', () => {
    const pets = [
      { pet_id: 'pet-a', client_id: 'client-1', name: 'Alpha', care_instructions: 'A notes' },
      { pet_id: 'pet-b', client_id: 'client-1', name: 'Bravo', care_instructions: 'B notes' },
    ];
    renderCard(makeProps(makePet({ pets })));
    // Switch to Bravo, enter edit, confirm the edit field shows Bravo's value.
    act(() => { fireEvent.click(chipFor('Bravo')); });
    expect(activeChipName()).toBe('Bravo');
    enterEdit();
    expect(screen.getByDisplayValue('Bravo')).toBeInTheDocument();
  });

  it('3. a same-index same-identity refresh does NOT overwrite unsaved edits', () => {
    const pet = makePet({ name: 'Alpha' });
    const { rerender } = renderCard(makeProps(pet));
    enterEdit();
    // User edits the name.
    act(() => { fireEvent.change(screen.getByDisplayValue('Alpha'), { target: { value: 'Alpha EDITED' } }); });
    expect(screen.getByDisplayValue('Alpha EDITED')).toBeInTheDocument();

    // Parent refreshes the SAME pet (same pet_id/request) with a new object ref.
    const refreshed = makePet({ name: 'Alpha' });
    act(() => { rerender(<CareCard {...makeProps(refreshed)} />); });

    // Unsaved edit must survive (edit mode active + same identity).
    expect(screen.getByDisplayValue('Alpha EDITED')).toBeInTheDocument();
  });

  it('4. edit mode blocks pet-tab switching', () => {
    const pets = [
      { pet_id: 'pet-a', client_id: 'client-1', name: 'Alpha' },
      { pet_id: 'pet-b', client_id: 'client-1', name: 'Bravo' },
    ];
    renderCard(makeProps(makePet({ pets })));
    enterEdit();
    // Attempt to switch to Bravo while editing; selection must not change.
    const bravoChip = chipFor('Bravo');
    act(() => { fireEvent.click(bravoChip); });
    expect(activeChipName()).toBe('Alpha');
  });

  it('5. cancel restores the selected pet authoritative values', () => {
    renderCard(makeProps(makePet({ name: 'Alpha' })));
    enterEdit();
    act(() => { fireEvent.change(screen.getByDisplayValue('Alpha'), { target: { value: 'Scratch' } }); });
    clickCancel();
    // Back to read mode showing the authoritative name; re-enter edit shows original.
    enterEdit();
    expect(screen.getByDisplayValue('Alpha')).toBeInTheDocument();
  });

  it('6. saving uses the active pet identity and the exact edited values (one call)', async () => {
    const pet = makePet({ petId: 'pet-a', name: 'Alpha' });
    const props = makeProps(pet);
    renderCard(props);
    enterEdit();
    act(() => { fireEvent.change(screen.getByDisplayValue('Alpha'), { target: { value: 'Alpha Renamed' } }); });

    await act(async () => { clickSave(); await Promise.resolve(); });

    expect(props.onUpdate).toHaveBeenCalledTimes(1);
    const payload = props.onUpdate.mock.calls[0][0];
    expect(payload).toMatchObject({ pet_id: 'pet-a', client_id: 'client-1', name: 'Alpha Renamed' });
    expect(payload).not.toHaveProperty('service_type');
  });

  it('7. an unrelated rerender (same pet reference) preserves user-entered form values', () => {
    const pet = makePet({ name: 'Alpha' });
    const props = makeProps(pet);
    const { rerender } = renderCard(props);
    enterEdit();
    act(() => { fireEvent.change(screen.getByDisplayValue('Alpha'), { target: { value: 'Typed Value' } }); });

    // Same pet reference rerender (unrelated parent rerender).
    act(() => { rerender(<CareCard {...props} />); });
    expect(screen.getByDisplayValue('Typed Value')).toBeInTheDocument();
  });

  it('8. switching requests (not editing) does not leak the previous request editable values', () => {
    const reqA = makePet({ requestId: 'A', petId: 'pet-a', name: 'Alpha' });
    const { rerender } = renderCard(makeProps(reqA));

    // Switch to a different request/pet at the same (index 0), NOT editing.
    const reqB = makePet({ requestId: 'B', petId: 'pet-b', name: 'Bravo' });
    act(() => { rerender(<CareCard {...makeProps(reqB)} />); });

    // Entering edit must show request B's values, never request A's.
    enterEdit();
    expect(screen.getByDisplayValue('Bravo')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('Alpha')).not.toBeInTheDocument();
  });

  it('9. add-pet auto-selection still shows the newly added pet', () => {
    const pets = [
      { pet_id: 'pet-a', client_id: 'client-1', name: 'Alpha' },
      { pet_id: 'pet-b', client_id: 'client-1', name: 'Bravo' },
    ];
    const { rerender } = renderCard(makeProps(makePet({ pets })));
    const withNew = makePet({
      pets: [
        { pet_id: 'pet-a', client_id: 'client-1', name: 'Alpha' },
        { pet_id: 'pet-b', client_id: 'client-1', name: 'Bravo' },
        { pet_id: 'pet-c', client_id: 'client-1', name: 'Charlie' },
      ],
    });
    withNew._newPetIndex = 2;
    act(() => { rerender(<CareCard {...makeProps(withNew)} />); });
    expect(activeChipName()).toBe('Charlie');
  });

  it('10. saving does not fire duplicate update calls on a single click', async () => {
    const props = makeProps(makePet({ name: 'Alpha' }));
    renderCard(props);
    enterEdit();
    await act(async () => { clickSave(); await Promise.resolve(); });
    expect(props.onUpdate).toHaveBeenCalledTimes(1);
  });
});
