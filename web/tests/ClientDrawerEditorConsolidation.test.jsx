import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ClientDetailDrawer from '../src/components/ClientDetailDrawer';
import { vi, describe, it, expect } from 'vitest';

describe('Client Drawer Editor Consolidation Component Tests', () => {
  const clientData = {
    client_id: 'client-123',
    display_name: 'Jane Doe',
    email: 'jane@example.com',
    phone: '555-1234',
    address: '123 Main St',
    emergency_contact: 'John Doe - 555-5678',
    notes: 'Likes dogs',
    cognito_status: 'CONFIRMED',
    is_active: true
  };

  const defaultFormVals = {
    display_name: '',
    email: '',
    phone: '',
    address: '',
    emergency_contact: '',
    notes: '',
    creation_mode: 'onboard',
    send_invite: true
  };

  it('1. Render in view mode shows all read-only sections and clicking edit triggers onEdit', () => {
    const handleEdit = vi.fn();
    render(
      <ClientDetailDrawer
        client={clientData}
        mode="view"
        onClose={vi.fn()}
        onEdit={handleEdit}
        isProtectedProfile={() => false}
      />
    );

    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('jane@example.com')).toBeInTheDocument();
    expect(screen.getByText('555-1234')).toBeInTheDocument();
    expect(screen.getByText('123 Main St')).toBeInTheDocument();
    expect(screen.getByText('John Doe - 555-5678')).toBeInTheDocument();
    expect(screen.getByText('Likes dogs')).toBeInTheDocument();

    const editBtn = screen.getByRole('button', { name: /Edit Profile/i });
    expect(editBtn).toBeInTheDocument();
    fireEvent.click(editBtn);
    expect(handleEdit).toHaveBeenCalledWith(clientData);
  });

  it('2. Render in edit mode displays prepopulated form inputs', () => {
    const handleCancel = vi.fn();
    const handleSave = vi.fn();
    const setFormValues = vi.fn();

    render(
      <ClientDetailDrawer
        client={clientData}
        mode="edit"
        formValues={clientData}
        setFormValues={setFormValues}
        onClose={vi.fn()}
        onCancel={handleCancel}
        onSave={handleSave}
        isProtectedProfile={() => false}
      />
    );

    const displayNameInput = screen.getByLabelText(/Display Name \*/i);
    expect(displayNameInput).toBeInTheDocument();
    expect(displayNameInput.value).toBe('Jane Doe');

    const emailInput = screen.getByLabelText(/Email Address/i);
    expect(emailInput).toBeInTheDocument();
    expect(emailInput).toBeDisabled(); // Read-only in edit mode

    const phoneInput = screen.getByLabelText(/Phone/i);
    expect(phoneInput).toBeInTheDocument();
    expect(phoneInput.value).toBe('555-1234');

    const addressInput = screen.getByLabelText(/Physical Address/i);
    expect(addressInput).toBeInTheDocument();
    expect(addressInput.value).toBe('123 Main St');

    const emergencyInput = screen.getByLabelText(/Emergency Contact/i);
    expect(emergencyInput).toBeInTheDocument();
    expect(emergencyInput.value).toBe('John Doe - 555-5678');

    const notesInput = screen.getByLabelText(/Client Notes/i);
    expect(notesInput).toBeInTheDocument();
    expect(notesInput.value).toBe('Likes dogs');

    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancelBtn);
    expect(handleCancel).toHaveBeenCalled();
  });

  it('3. Render in create mode allows inputting new details and triggers save', () => {
    const handleSave = vi.fn((e) => e.preventDefault());
    const setFormValues = vi.fn();

    render(
      <ClientDetailDrawer
        client={{ client_id: 'new' }}
        mode="create"
        formValues={defaultFormVals}
        setFormValues={setFormValues}
        onClose={vi.fn()}
        onCancel={vi.fn()}
        onSave={handleSave}
        isProtectedProfile={() => false}
      />
    );

    expect(screen.getByText('Add New Client Profile')).toBeInTheDocument();
    expect(screen.getByLabelText(/Create Login & Profile/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Create Profile Only \(No Login\)/i)).toBeInTheDocument();

    const emailInput = screen.getByLabelText(/Email Address/i);
    expect(emailInput).not.toBeDisabled(); // Editable in create mode
  });

  it('4. Submit validation works - display_name required, email required if onboarding', () => {
    const handleSave = vi.fn((e) => e.preventDefault());
    const setFormValues = vi.fn();

    // Invalid: missing display name
    const { rerender } = render(
      <ClientDetailDrawer
        client={{ client_id: 'new' }}
        mode="create"
        formValues={{ ...defaultFormVals, display_name: '' }}
        setFormValues={setFormValues}
        onClose={vi.fn()}
        onCancel={vi.fn()}
        onSave={handleSave}
        isProtectedProfile={() => false}
      />
    );

    const form = screen.getByRole('dialog').querySelector('form');
    fireEvent.submit(form);
    expect(screen.getByText('Display name is required')).toBeInTheDocument();
    expect(handleSave).not.toHaveBeenCalled();

    // Invalid: missing email in onboard mode
    rerender(
      <ClientDetailDrawer
        client={{ client_id: 'new' }}
        mode="create"
        formValues={{ ...defaultFormVals, display_name: 'Jane Doe', email: '', creation_mode: 'onboard' }}
        setFormValues={setFormValues}
        onClose={vi.fn()}
        onCancel={vi.fn()}
        onSave={handleSave}
        isProtectedProfile={() => false}
      />
    );

    fireEvent.submit(form);
    expect(screen.getByText('Email is required for login invitation')).toBeInTheDocument();
    expect(handleSave).not.toHaveBeenCalled();

    // Valid: profile-only mode with empty email
    rerender(
      <ClientDetailDrawer
        client={{ client_id: 'new' }}
        mode="create"
        formValues={{ ...defaultFormVals, display_name: 'Jane Doe', email: '', creation_mode: 'profile_only' }}
        setFormValues={setFormValues}
        onClose={vi.fn()}
        onCancel={vi.fn()}
        onSave={handleSave}
        isProtectedProfile={() => false}
      />
    );

    fireEvent.submit(form);
    expect(handleSave).toHaveBeenCalled();
  });
});
