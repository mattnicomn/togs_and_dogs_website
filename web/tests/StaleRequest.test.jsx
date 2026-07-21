import React, { useState, useRef } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { listAdminClientPets } from '../src/api/client';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock listAdminClientPets API
vi.mock('../src/api/client', () => ({
  listAdminClientPets: vi.fn()
}));

// Test Harness matching AdminDashboard's state and sequence checks exactly
const StaleRequestHarness = ({ clientList }) => {
  const [editingClientId, setEditingClientId] = useState(null);
  const [clientPets, setClientPets] = useState([]);
  const [isClientPetsLoading, setIsClientPetsLoading] = useState(false);

  const clientPetRequestSeqRef = useRef(0);
  const activeClientDetailIdRef = useRef(null);

  const handleEditClient = (client) => {
    setEditingClientId(client.client_id);

    clientPetRequestSeqRef.current += 1;
    const currentSeq = clientPetRequestSeqRef.current;
    const currentClientId = client.client_id;
    activeClientDetailIdRef.current = currentClientId;

    setClientPets([]);
    setIsClientPetsLoading(true);

    if (currentClientId && currentClientId !== 'new') {
      listAdminClientPets(currentClientId)
        .then(resp => {
          if (currentSeq === clientPetRequestSeqRef.current && activeClientDetailIdRef.current === currentClientId) {
            const pets = (resp && Array.isArray(resp.pets) ? resp.pets : []).filter(p => p && p.pet_id);
            setClientPets(pets);
            setIsClientPetsLoading(false);
          }
        })
        .catch(() => {
          if (currentSeq === clientPetRequestSeqRef.current && activeClientDetailIdRef.current === currentClientId) {
            setClientPets([]);
            setIsClientPetsLoading(false);
          }
        });
    } else {
      setIsClientPetsLoading(false);
    }
  };

  const closeClientDetail = () => {
    setEditingClientId(null);
    setClientPets([]);
    setIsClientPetsLoading(false);

    clientPetRequestSeqRef.current += 1;
    activeClientDetailIdRef.current = null;
  };

  return (
    <div>
      <div data-testid="active-id">{editingClientId || 'none'}</div>
      <div data-testid="loading-state">{isClientPetsLoading ? 'Loading' : 'Idle'}</div>
      <div data-testid="pets-count">{clientPets.length}</div>
      <ul data-testid="pets-list">
        {clientPets.map(p => <li key={p.pet_id}>{p.name}</li>)}
      </ul>
      {clientList.map(c => (
        <button key={c.client_id} data-testid={`select-${c.client_id}`} onClick={() => handleEditClient(c)}>
          Select {c.display_name}
        </button>
      ))}
      <button data-testid="close-btn" onClick={closeClientDetail}>Close</button>
    </div>
  );
};

describe('Stale-Request Race-Condition Guard Tests', () => {
  const clients = [
    { client_id: 'client-A', display_name: 'Client A' },
    { client_id: 'client-B', display_name: 'Client B' }
  ];

  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('1. stale request sequence matches expected behavior', async () => {
    // Setup deferred promises for listAdminClientPets calls to control resolution timing
    let resolveA;
    const promiseA = new Promise((resolve) => { resolveA = resolve; });
    
    let resolveB;
    const promiseB = new Promise((resolve) => { resolveB = resolve; });

    listAdminClientPets.mockImplementation((id) => {
      if (id === 'client-A') return promiseA;
      if (id === 'client-B') return promiseB;
      return Promise.resolve({ pets: [] });
    });

    render(<StaleRequestHarness clientList={clients} />);

    // Step 1: select Client A (starts request A, unresolved)
    fireEvent.click(screen.getByTestId('select-client-A'));
    expect(screen.getByTestId('active-id').textContent).toBe('client-A');
    expect(screen.getByTestId('loading-state').textContent).toBe('Loading');
    expect(screen.getByTestId('pets-count').textContent).toBe('0');

    // Step 2: select Client B immediately (starts request B)
    // Switching clients should clear prior visible pets immediately
    fireEvent.click(screen.getByTestId('select-client-B'));
    expect(screen.getByTestId('active-id').textContent).toBe('client-B');
    expect(screen.getByTestId('loading-state').textContent).toBe('Loading');
    expect(screen.getByTestId('pets-count').textContent).toBe('0');

    // Step 3: resolve Client B response
    resolveB({ pets: [{ pet_id: 'pet-2', name: 'Max' }] });
    await waitFor(() => {
      expect(screen.getByTestId('pets-count').textContent).toBe('1');
      expect(screen.getByText('Max')).toBeInTheDocument();
      expect(screen.getByTestId('loading-state').textContent).toBe('Idle');
    });

    // Step 4: resolve Client A response afterward
    resolveA({ pets: [{ pet_id: 'pet-1', name: 'Buddy' }] });
    
    // Wait to ensure Client A resolve does NOT overwrite Client B
    await new Promise(r => setTimeout(r, 50));
    expect(screen.getByTestId('pets-count').textContent).toBe('1');
    expect(screen.queryByText('Buddy')).not.toBeInTheDocument();
    expect(screen.getByText('Max')).toBeInTheDocument();
  });

  it('2. late empty result cannot clear active client pets', async () => {
    let resolveA;
    const promiseA = new Promise((resolve) => { resolveA = resolve; });
    listAdminClientPets.mockImplementation((id) => id === 'client-A' ? promiseA : Promise.resolve({ pets: [{ pet_id: 'pet-2', name: 'Max' }] }));

    render(<StaleRequestHarness clientList={clients} />);

    // Select Client A
    fireEvent.click(screen.getByTestId('select-client-A'));
    
    // Select Client B and resolve immediately
    fireEvent.click(screen.getByTestId('select-client-B'));
    await waitFor(() => {
      expect(screen.getByText('Max')).toBeInTheDocument();
    });

    // Resolve A with empty array/null
    resolveA({ pets: [] });
    await new Promise(r => setTimeout(r, 50));
    expect(screen.getByText('Max')).toBeInTheDocument();
  });

  it('3. late error cannot replace active client state', async () => {
    let rejectA;
    const promiseA = new Promise((_, reject) => { rejectA = reject; });
    listAdminClientPets.mockImplementation((id) => id === 'client-A' ? promiseA : Promise.resolve({ pets: [{ pet_id: 'pet-2', name: 'Max' }] }));

    render(<StaleRequestHarness clientList={clients} />);

    // Select Client A
    fireEvent.click(screen.getByTestId('select-client-A'));
    
    // Select Client B
    fireEvent.click(screen.getByTestId('select-client-B'));
    await waitFor(() => {
      expect(screen.getByText('Max')).toBeInTheDocument();
    });

    // Reject A
    rejectA(new Error('Late failure'));
    await new Promise(r => setTimeout(r, 50));
    expect(screen.getByText('Max')).toBeInTheDocument();
    expect(screen.getByTestId('loading-state').textContent).toBe('Idle');
  });

  it('4. drawer close invalidates an unresolved request', async () => {
    let resolveA;
    const promiseA = new Promise((resolve) => { resolveA = resolve; });
    listAdminClientPets.mockImplementation(() => promiseA);

    render(<StaleRequestHarness clientList={clients} />);

    // Select Client A
    fireEvent.click(screen.getByTestId('select-client-A'));
    expect(screen.getByTestId('loading-state').textContent).toBe('Loading');

    // Close drawer
    fireEvent.click(screen.getByTestId('close-btn'));
    expect(screen.getByTestId('loading-state').textContent).toBe('Idle');
    expect(screen.getByTestId('active-id').textContent).toBe('none');

    // Resolve A
    resolveA({ pets: [{ pet_id: 'pet-1', name: 'Buddy' }] });
    await new Promise(r => setTimeout(r, 50));
    expect(screen.getByTestId('pets-count').textContent).toBe('0');
    expect(screen.getByTestId('loading-state').textContent).toBe('Idle');
  });
});
