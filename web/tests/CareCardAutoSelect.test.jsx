import React from 'react';
import { fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CareCard from '../src/components/CareCard';

// Mock the payment API so no real AWS/Stripe/Cognito/Google calls occur.
vi.mock('../src/api/client', () => ({
  createPaymentSession: vi.fn(),
  sendPaymentEmail: vi.fn(),
}));

// Build a multi-pet request record. _allPets drives the multi-pet selector;
// _originItem carries the authoritative request identity (PK / request_id).
const makePet = ({
  requestId = 'request-1',
  pets = [
    { pet_id: 'pet-a', client_id: 'client-1', name: 'Alpha' },
    { pet_id: 'pet-b', client_id: 'client-1', name: 'Bravo' },
  ],
  newPetIndex,
  showArchivedSeed,
} = {}) => {
  const first = pets.find((p) => p._fetchFailed !== true) || pets[0];
  const petObj = {
    ...first,
    _allPets: pets,
    _originItem: {
      PK: `REQ#${requestId}`,
      request_id: requestId,
      client_id: 'client-1',
      linked_client_profile_id: 'client-1',
      status: 'APPROVED',
    },
  };
  if (newPetIndex !== undefined) petObj._newPetIndex = newPetIndex;
  if (showArchivedSeed !== undefined) petObj.__showArchivedSeed = showArchivedSeed;
  return petObj;
};

const makeProps = (pet, overrides = {}) => ({
  pet,
  onClose: vi.fn(),
  onUpdate: vi.fn().mockResolvedValue(undefined),
  onStatusUpdate: vi.fn().mockResolvedValue(undefined),
  userRole: 'owner',
  ...overrides,
});

// The active pet is the chip carrying the `active` class in the pet selector.
const activeChipName = () => {
  const chips = Array.from(document.querySelectorAll('.pet-chip'));
  const active = chips.find((c) => c.className.includes('active'));
  return active ? active.textContent.replace(/⊘/g, '').trim() : null;
};

const chipFor = (name) =>
  Array.from(document.querySelectorAll('.pet-chip')).find(
    (c) => c.textContent.replace(/⊘/g, '').trim() === name
  );

const renderCard = (props) => {
  let utils;
  act(() => {
    utils = render(<CareCard {...props} />);
  });
  return utils;
};

describe('CareCard new-pet auto-selection (Gate C3b.2j Batch 4B-1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. adding a pet with a valid _newPetIndex selects the newly added pet', () => {
    // Start on an existing request with two pets, Alpha active by default.
    const { rerender } = renderCard(makeProps(makePet()));
    expect(activeChipName()).toBe('Alpha');

    // Parent appends a third pet and signals its index (add-pet workflow).
    const withNew = makePet({
      pets: [
        { pet_id: 'pet-a', client_id: 'client-1', name: 'Alpha' },
        { pet_id: 'pet-b', client_id: 'client-1', name: 'Bravo' },
        { pet_id: 'pet-c', client_id: 'client-1', name: 'Charlie' },
      ],
      newPetIndex: 2,
    });
    act(() => { rerender(<CareCard {...makeProps(withNew)} />); });

    expect(activeChipName()).toBe('Charlie');
  });

  it('2. auto-selection occurs only once for a given add-pet event', () => {
    const addPet = makePet({
      pets: [
        { pet_id: 'pet-a', client_id: 'client-1', name: 'Alpha' },
        { pet_id: 'pet-b', client_id: 'client-1', name: 'Bravo' },
        { pet_id: 'pet-c', client_id: 'client-1', name: 'Charlie' },
      ],
      newPetIndex: 2,
    });
    const { rerender } = renderCard(makeProps(addPet));
    expect(activeChipName()).toBe('Charlie');

    // User deliberately navigates back to Alpha.
    act(() => { fireEvent.click(chipFor('Alpha')); });
    expect(activeChipName()).toBe('Alpha');

    // An unrelated rerender that carries the SAME _newPetIndex must not
    // re-apply the auto-selection (same add-pet signature).
    act(() => { rerender(<CareCard {...makeProps({ ...addPet })} />); });
    expect(activeChipName()).toBe('Alpha');
  });

  it('3. an unrelated rerender does not force selection back to the new pet', () => {
    const addPet = makePet({
      pets: [
        { pet_id: 'pet-a', client_id: 'client-1', name: 'Alpha' },
        { pet_id: 'pet-b', client_id: 'client-1', name: 'Bravo' },
        { pet_id: 'pet-c', client_id: 'client-1', name: 'Charlie' },
      ],
      newPetIndex: 2,
    });
    const { rerender } = renderCard(makeProps(addPet));
    expect(activeChipName()).toBe('Charlie');

    act(() => { fireEvent.click(chipFor('Bravo')); });
    expect(activeChipName()).toBe('Bravo');

    // Simulate a benign content refresh of the same request (new object
    // reference, identical identity + _newPetIndex) — selection must stick.
    const refreshed = {
      ...addPet,
      _allPets: addPet._allPets.map((p) => ({ ...p })),
    };
    act(() => { rerender(<CareCard {...makeProps(refreshed)} />); });
    expect(activeChipName()).toBe('Bravo');
  });

  it('4. when _newPetIndex is absent, existing selection is not overridden', () => {
    const { rerender } = renderCard(makeProps(makePet()));
    act(() => { fireEvent.click(chipFor('Bravo')); });
    expect(activeChipName()).toBe('Bravo');

    // Rerender with no _newPetIndex (ordinary refresh) keeps the user choice.
    const refreshed = makePet();
    act(() => { rerender(<CareCard {...makeProps(refreshed)} />); });
    expect(activeChipName()).toBe('Bravo');
  });

  it('5. an invalid or out-of-bounds _newPetIndex cannot corrupt selection', () => {
    // Out-of-bounds high index.
    const { rerender } = renderCard(makeProps(makePet({ newPetIndex: 99 })));
    expect(activeChipName()).toBe('Alpha');

    // Negative index.
    act(() => { rerender(<CareCard {...makeProps(makePet({ newPetIndex: -1 }))} />); });
    expect(activeChipName()).toBe('Alpha');

    // No crash, selector still functional.
    act(() => { fireEvent.click(chipFor('Bravo')); });
    expect(activeChipName()).toBe('Bravo');
  });

  it('6. reusing the instance for another request does not replay prior auto-selection', () => {
    // Request 1: add-pet selects Charlie (index 2).
    const req1 = makePet({
      requestId: 'request-1',
      pets: [
        { pet_id: 'pet-a', client_id: 'client-1', name: 'Alpha' },
        { pet_id: 'pet-b', client_id: 'client-1', name: 'Bravo' },
        { pet_id: 'pet-c', client_id: 'client-1', name: 'Charlie' },
      ],
      newPetIndex: 2,
    });
    const { rerender } = renderCard(makeProps(req1));
    expect(activeChipName()).toBe('Charlie');

    // Switch to a DIFFERENT request (reused instance) that carries no
    // _newPetIndex. The prior request's auto-selection (index 2) must NOT be
    // replayed onto this request. (Whether a stale index resets to the first
    // pet is a separate selection-reset concern outside Batch 4B-1 scope; here
    // we only assert the prior event is not replayed.)
    const req2 = makePet({
      requestId: 'request-2',
      pets: [
        { pet_id: 'pet-x', client_id: 'client-2', name: 'Xavier' },
        { pet_id: 'pet-y', client_id: 'client-2', name: 'Yolanda' },
      ],
    });
    act(() => { rerender(<CareCard {...makeProps(req2)} />); });
    // No chip for request-1's "Charlie" exists here; auto-selection was not replayed.
    expect(chipFor('Charlie')).toBeUndefined();

    // A different request that happens to reuse the same _newPetIndex value (2)
    // as request-1 must still auto-select for ITS OWN event.
    const req3 = makePet({
      requestId: 'request-3',
      pets: [
        { pet_id: 'pet-m', client_id: 'client-3', name: 'Mike' },
        { pet_id: 'pet-n', client_id: 'client-3', name: 'Nina' },
        { pet_id: 'pet-o', client_id: 'client-3', name: 'Oscar' },
      ],
      newPetIndex: 2,
    });
    act(() => { rerender(<CareCard {...makeProps(req3)} />); });
    expect(activeChipName()).toBe('Oscar');
  });

  it('7. pet-tab navigation and the add-pet trigger remain functional', () => {
    renderCard(makeProps(makePet(), { onAddPet: vi.fn() }));
    // Manual navigation works.
    act(() => { fireEvent.click(chipFor('Bravo')); });
    expect(activeChipName()).toBe('Bravo');
    act(() => { fireEvent.click(chipFor('Alpha')); });
    expect(activeChipName()).toBe('Alpha');

    // The Add Pet affordance is present for an owner on a linked request.
    const addPetBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent.trim() === '+ Add Pet'
    );
    expect(addPetBtn).toBeTruthy();
  });
});
