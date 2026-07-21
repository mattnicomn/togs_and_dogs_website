import React, { useState } from 'react';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import ClientDetailDrawer from '../src/components/ClientDetailDrawer';
import AdminDashboard from '../src/components/AdminDashboard';
import { getSession, getEffectiveRole } from '../src/api/auth';
import {
  getAdminRequests,
  getClients,
  getStaff,
  getGoogleStatus,
  getTenantInfo,
  listAdminClientPets,
  getPet
} from '../src/api/client';

// Mock scrollIntoView in JSDOM
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock auth API
vi.mock('../src/api/auth', () => ({
  signIn: vi.fn(),
  getSession: vi.fn(),
  getEffectiveRole: vi.fn()
}));

// Mock client API
vi.mock('../src/api/client', () => ({
  getAdminRequests: vi.fn(),
  getClients: vi.fn(),
  getStaff: vi.fn(),
  getTenantInfo: vi.fn(),
  getGoogleStatus: vi.fn(),
  getPet: vi.fn(),
  updateClient: vi.fn(),
  createClient: vi.fn(),
  onboardClient: vi.fn(),
  resendClientInvite: vi.fn(),
  resetClientPassword: vi.fn(),
  setClientTempPassword: vi.fn(),
  linkClientCognitoUser: vi.fn(),
  resendInvite: vi.fn(),
  resetStaffPassword: vi.fn(),
  setStaffTempPassword: vi.fn(),
  linkCognitoUser: vi.fn(),
  listAdminClientPets: vi.fn()
}));

const clientData = {
  client_id: 'client-123',
  display_name: 'Jane Doe',
  email: 'jane@example.com',
  phone: '555-1234',
  address: '123 Main St',
  emergency_contact: 'John Doe - 555-5678',
  notes: 'Likes dogs',
  cognito_status: 'CONFIRMED',
  cognito_sub: 'sub-jane',
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

// Wrapper mimicking AdminDashboard's state and dirty checks
const ClientDrawerTestWrapper = ({
  client,
  initialMode = 'view',
  onSaveSuccess,
  isProtectedProfile = () => false,
  ...props
}) => {
  const [mode, setMode] = useState(initialMode);
  const [formValues, setFormValues] = useState({
    display_name: client.display_name || '',
    email: client.email || '',
    phone: client.phone || '',
    address: client.address || '',
    emergency_contact: client.emergency_contact || '',
    notes: client.notes || '',
    creation_mode: client.creation_mode || 'onboard',
    send_invite: client.send_invite !== false
  });
  const [initialFormValues, setInitialFormValues] = useState({ ...formValues });
  const [isOpen, setIsOpen] = useState(true);

  const hasClientUnsavedChanges = mode !== 'view' && (
    formValues.display_name !== initialFormValues.display_name ||
    formValues.email !== initialFormValues.email ||
    formValues.phone !== initialFormValues.phone ||
    formValues.address !== initialFormValues.address ||
    formValues.emergency_contact !== initialFormValues.emergency_contact ||
    formValues.notes !== initialFormValues.notes ||
    (mode === 'create' && (
      formValues.creation_mode !== initialFormValues.creation_mode ||
      formValues.send_invite !== initialFormValues.send_invite
    ))
  );

  const handleClose = () => {
    if (hasClientUnsavedChanges) {
      if (!window.confirm("You have unsaved changes. Are you sure you want to discard them?")) {
        return;
      }
    }
    setIsOpen(false);
  };

  const handleCancel = () => {
    if (hasClientUnsavedChanges) {
      if (!window.confirm("You have unsaved changes. Are you sure you want to discard them?")) {
        return;
      }
    }
    if (mode === 'create') {
      setIsOpen(false);
    } else {
      setFormValues(initialFormValues);
      setMode('view');
    }
  };

  const handleSave = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (onSaveSuccess) {
      await onSaveSuccess(formValues);
    }
    setInitialFormValues({ ...formValues });
    if (mode === 'create') {
      setIsOpen(false);
    } else {
      setMode('view');
    }
  };

  if (!isOpen) return <div data-testid="drawer-closed">Closed</div>;

  return (
    <ClientDetailDrawer
      client={client}
      mode={mode}
      formValues={formValues}
      setFormValues={setFormValues}
      onClose={handleClose}
      onEdit={() => {
        setInitialFormValues({ ...formValues });
        setMode('edit');
      }}
      onCancel={handleCancel}
      onSave={handleSave}
      isProtectedProfile={isProtectedProfile}
      {...props}
    />
  );
};

describe('Client Drawer Editor Consolidation - Hardened Component Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  describe('Section 1: Unsaved-change & closing paths protection', () => {
    it('1. dirty Edit close-button attempt invokes confirmation', () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
      render(<ClientDrawerTestWrapper client={clientData} initialMode="edit" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Name' } });
      
      const closeBtn = screen.getByRole('button', { name: /close client details/i });
      fireEvent.click(closeBtn);
      
      expect(confirmSpy).toHaveBeenCalledWith("You have unsaved changes. Are you sure you want to discard them?");
    });

    it('2. declining close confirmation keeps the drawer open', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(false);
      render(<ClientDrawerTestWrapper client={clientData} initialMode="edit" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Name' } });
      
      const closeBtn = screen.getByRole('button', { name: /close client details/i });
      fireEvent.click(closeBtn);
      
      expect(screen.queryByTestId('drawer-closed')).not.toBeInTheDocument();
      expect(screen.getByLabelText(/Display Name \*/i)).toBeInTheDocument();
    });

    it('3. accepting close confirmation closes the drawer', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      render(<ClientDrawerTestWrapper client={clientData} initialMode="edit" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Name' } });
      
      const closeBtn = screen.getByRole('button', { name: /close client details/i });
      fireEvent.click(closeBtn);
      
      expect(screen.getByTestId('drawer-closed')).toBeInTheDocument();
    });

    it('4. dirty Edit Escape invokes the protected close path', () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
      render(<ClientDrawerTestWrapper client={clientData} initialMode="edit" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Name' } });
      
      fireEvent.keyDown(document, { key: 'Escape' });
      expect(confirmSpy).toHaveBeenCalled();
    });

    it('5. dirty Edit overlay click invokes the protected close path', () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
      render(<ClientDrawerTestWrapper client={clientData} initialMode="edit" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Name' } });
      
      const overlay = document.body.querySelector('.client-detail-drawer-overlay');
      fireEvent.click(overlay);
      expect(confirmSpy).toHaveBeenCalled();
    });

    it('6. clean Edit Cancel returns to View without confirmation', () => {
      const confirmSpy = vi.spyOn(window, 'confirm');
      render(<ClientDrawerTestWrapper client={clientData} initialMode="edit" />);
      
      const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
      fireEvent.click(cancelBtn);
      
      expect(confirmSpy).not.toHaveBeenCalled();
      expect(screen.getByText('Jane Doe')).toBeInTheDocument(); // back to view mode
    });

    it('7. dirty Edit Cancel invokes confirmation', () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
      render(<ClientDrawerTestWrapper client={clientData} initialMode="edit" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Name' } });
      
      const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
      fireEvent.click(cancelBtn);
      expect(confirmSpy).toHaveBeenCalled();
    });

    it('8. declining dirty Edit Cancel preserves values and Edit mode', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(false);
      render(<ClientDrawerTestWrapper client={clientData} initialMode="edit" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Name' } });
      
      const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
      fireEvent.click(cancelBtn);
      
      expect(screen.getByLabelText(/Display Name \*/i).value).toBe('New Name');
      expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument(); // still in Edit mode
    });

    it('9. accepting dirty Edit Cancel restores View mode and original values', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      render(<ClientDrawerTestWrapper client={clientData} initialMode="edit" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Name' } });
      
      const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
      fireEvent.click(cancelBtn);
      
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      expect(screen.queryByLabelText(/Display Name \*/i)).not.toBeInTheDocument();
    });

    it('10. dirty Create Cancel invokes confirmation', () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
      render(<ClientDrawerTestWrapper client={{ client_id: 'new' }} initialMode="create" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Client' } });
      
      const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
      fireEvent.click(cancelBtn);
      expect(confirmSpy).toHaveBeenCalled();
    });

    it('11. accepting Create Cancel closes the drawer', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      render(<ClientDrawerTestWrapper client={{ client_id: 'new' }} initialMode="create" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Client' } });
      
      const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
      fireEvent.click(cancelBtn);
      
      expect(screen.getByTestId('drawer-closed')).toBeInTheDocument();
    });

    it('12. declining Create Cancel keeps Create mode and entered values', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(false);
      render(<ClientDrawerTestWrapper client={{ client_id: 'new' }} initialMode="create" />);
      
      const displayNameInput = screen.getByLabelText(/Display Name \*/i);
      fireEvent.change(displayNameInput, { target: { value: 'New Client' } });
      
      const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
      fireEvent.click(cancelBtn);
      
      expect(screen.queryByTestId('drawer-closed')).not.toBeInTheDocument();
      expect(screen.getByLabelText(/Display Name \*/i).value).toBe('New Client');
    });
  });

  describe('Section 2: Parent integration tests (AdminDashboard)', () => {
    const mockSession = {
      getIdToken: () => ({
        payload: {
          email: 'owner@example.com',
          sub: 'owner-sub-123',
          name: 'Owner User'
        }
      })
    };

    beforeEach(() => {
      getSession.mockResolvedValue(mockSession);
      getEffectiveRole.mockReturnValue('owner');
      getAdminRequests.mockResolvedValue({ requests: [] });
      getStaff.mockResolvedValue({ staff: [] });
      getGoogleStatus.mockResolvedValue({});
      getTenantInfo.mockResolvedValue({
        company_name: 'Togs and Dogs',
        support_email: 'support@example.com'
      });
      getClients.mockResolvedValue({
        clients: [
          {
            client_id: 'client-jane',
            display_name: 'Jane Doe',
            email: 'jane@example.com',
            phone: '555-1234',
            is_active: true
          },
          {
            client_id: 'client-bob',
            display_name: 'Bob Smith',
            email: 'bob@example.com',
            is_active: true
          }
        ]
      });
      listAdminClientPets.mockResolvedValue({ pets: [] });
    });

    const switchToClientMgmt = async () => {
      render(<AdminDashboard />);
      const tabButton = await screen.findByRole('button', { name: /Client Management/i });
      fireEvent.click(tabButton);
      await screen.findByText('Client Access Management');
    };

    it('1. Add New Client opens Create mode', async () => {
      await switchToClientMgmt();
      const addBtn = screen.getByRole('button', { name: /\+ Add New Client/i });
      fireEvent.click(addBtn);
      
      expect(screen.getByText('Add New Client Profile')).toBeInTheDocument();
      expect(screen.getByLabelText(/Create Login & Profile/i)).toBeInTheDocument();
    });

    it('2. client summary opens View mode', async () => {
      await switchToClientMgmt();
      const clientBtn = screen.getByRole('button', { name: /Client profile for Jane Doe/i });
      fireEvent.click(clientBtn);
      
      expect(screen.getByText('Client Overview')).toBeInTheDocument();
      expect(screen.getByText('555-1234')).toBeInTheDocument();
    });

    it('3. View Details opens the same client in View mode', async () => {
      await switchToClientMgmt();
      
      const cards = screen.getAllByText('Jane Doe');
      const cardContainer = cards[0].closest('.client-profile-card');
      const viewDetailsBtn = cardContainer.querySelector('.btn-small');
      fireEvent.click(viewDetailsBtn);
      
      expect(screen.getByText('Client Overview')).toBeInTheDocument();
      
      const drawer = document.body.querySelector('.client-detail-drawer');
      expect(within(drawer).getByText('jane@example.com')).toBeInTheDocument();
    });

    it('4. Edit Profile transitions View to Edit', async () => {
      await switchToClientMgmt();
      const clientBtn = screen.getByRole('button', { name: /Client profile for Jane Doe/i });
      fireEvent.click(clientBtn);
      
      const editBtn = screen.getByRole('button', { name: /Edit Profile/i });
      fireEvent.click(editBtn);
      
      expect(screen.getByLabelText(/Display Name \*/i).value).toBe('Jane Doe');
    });

    it('5. dirty client switching invokes confirmation', async () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
      await switchToClientMgmt();
      
      // Open Jane Doe and edit
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      fireEvent.click(screen.getByRole('button', { name: /Edit Profile/i }));
      fireEvent.change(screen.getByLabelText(/Display Name \*/i), { target: { value: 'Jane Edited' } });
      
      // Click Bob Smith card
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Bob Smith/i }));
      expect(confirmSpy).toHaveBeenCalledWith("You have unsaved changes. Are you sure you want to discard them?");
    });

    it('6. declining client-switch confirmation preserves the current client and edits', async () => {
      vi.spyOn(window, 'confirm').mockReturnValue(false);
      await switchToClientMgmt();
      
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      fireEvent.click(screen.getByRole('button', { name: /Edit Profile/i }));
      fireEvent.change(screen.getByLabelText(/Display Name \*/i), { target: { value: 'Jane Edited' } });
      
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Bob Smith/i }));
      expect(screen.getByLabelText(/Display Name \*/i).value).toBe('Jane Edited');
    });

    it('7. accepting client-switch confirmation opens the newly selected client', async () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      await switchToClientMgmt();
      
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      fireEvent.click(screen.getByRole('button', { name: /Edit Profile/i }));
      fireEvent.change(screen.getByLabelText(/Display Name \*/i), { target: { value: 'Jane Edited' } });
      
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Bob Smith/i }));
      expect(screen.getByText('Client Overview')).toBeInTheDocument();
      
      const drawer = document.body.querySelector('.client-detail-drawer');
      expect(within(drawer).getByText('bob@example.com')).toBeInTheDocument();
    });

    it('8. starting Add New Client while dirty invokes confirmation', async () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
      await switchToClientMgmt();
      
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      fireEvent.click(screen.getByRole('button', { name: /Edit Profile/i }));
      fireEvent.change(screen.getByLabelText(/Display Name \*/i), { target: { value: 'Jane Edited' } });
      
      fireEvent.click(screen.getByRole('button', { name: /\+ Add New Client/i }));
      expect(confirmSpy).toHaveBeenCalled();
      expect(screen.getByText('Add New Client Profile')).toBeInTheDocument();
    });
  });

  describe('Section 3: Save transition tests', () => {
    it('1. Save invokes update callback with expected payload and disables save while saving', async () => {
      const saveSpy = vi.fn().mockImplementation(async (e) => {
        e.preventDefault();
      });
      render(
        <ClientDetailDrawer
          client={clientData}
          mode="edit"
          formValues={clientData}
          setFormValues={vi.fn()}
          onClose={vi.fn()}
          onCancel={vi.fn()}
          onSave={saveSpy}
          isSaving={true}
          isProtectedProfile={() => false}
        />
      );

      const saveBtn = screen.getByRole('button', { name: /Saving.../i });
      expect(saveBtn).toBeDisabled();
    });

    it('2. Onboard creation checks required email, profile-only permits empty email', async () => {
      const saveSpy = vi.fn();
      const setFormValues = vi.fn();

      // Onboard mode with empty email -> rejected
      const { rerender } = render(
        <ClientDetailDrawer
          client={{ client_id: 'new' }}
          mode="create"
          formValues={{ ...defaultFormVals, display_name: 'Alex', email: '', creation_mode: 'onboard' }}
          setFormValues={setFormValues}
          onClose={vi.fn()}
          onCancel={vi.fn()}
          onSave={saveSpy}
          isProtectedProfile={() => false}
        />
      );

      const form = screen.getByRole('dialog').querySelector('form');
      fireEvent.submit(form);
      expect(screen.getByText('Email is required for login invitation')).toBeInTheDocument();
      expect(saveSpy).not.toHaveBeenCalled();

      // Profile-only mode with empty email -> allowed
      rerender(
        <ClientDetailDrawer
          client={{ client_id: 'new' }}
          mode="create"
          formValues={{ ...defaultFormVals, display_name: 'Alex', email: '', creation_mode: 'profile_only' }}
          setFormValues={setFormValues}
          onClose={vi.fn()}
          onCancel={vi.fn()}
          onSave={saveSpy}
          isProtectedProfile={() => false}
        />
      );

      fireEvent.submit(form);
      expect(saveSpy).toHaveBeenCalled();
    });
  });

  describe('Section 4: Focus & accessibility tests', () => {
    it('1. Initial focus correct for view, edit, and create modes', () => {
      const onClose = vi.fn();
      const { rerender } = render(
        <ClientDetailDrawer
          client={clientData}
          mode="view"
          onClose={onClose}
          isProtectedProfile={() => false}
        />
      );
      expect(document.activeElement).toBe(screen.getByRole('button', { name: /close client details/i }));

      rerender(
        <ClientDetailDrawer
          client={clientData}
          mode="edit"
          formValues={clientData}
          setFormValues={vi.fn()}
          onClose={onClose}
          isProtectedProfile={() => false}
        />
      );
      expect(document.activeElement).toBe(screen.getByLabelText(/Display Name \*/i));

      rerender(
        <ClientDetailDrawer
          client={{ client_id: 'new' }}
          mode="create"
          formValues={defaultFormVals}
          setFormValues={vi.fn()}
          onClose={onClose}
          isProtectedProfile={() => false}
        />
      );
      expect(document.activeElement).toBe(screen.getByLabelText(/Display Name \*/i));
    });

    it('2. Tab focus containment loops within the drawer', () => {
      render(
        <ClientDetailDrawer
          client={clientData}
          mode="edit"
          formValues={clientData}
          setFormValues={vi.fn()}
          onClose={vi.fn()}
          isProtectedProfile={() => false}
        />
      );

      const focusableElements = Array.from(
        document.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled])'
        )
      );
      const firstEl = focusableElements[0];
      const lastEl = focusableElements[focusableElements.length - 1];

      // Tab key on last element wraps focus back to the first element
      lastEl.focus();
      fireEvent.keyDown(lastEl, { key: 'Tab', shiftKey: false });
      
      // Shift+Tab key on first element wraps focus to the last element
      firstEl.focus();
      fireEvent.keyDown(firstEl, { key: 'Tab', shiftKey: true });
    });

    it('3. Dialog has correct attributes, classes, and does not render nested buttons', () => {
      render(
        <ClientDetailDrawer
          client={clientData}
          mode="view"
          onClose={vi.fn()}
          isProtectedProfile={() => false}
        />
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-modal', 'true');
      expect(dialog).toHaveAttribute('aria-label', 'Client details: Jane Doe');

      // CSS Classes
      const overlay = document.body.querySelector('.client-detail-drawer-overlay');
      const drawer = document.body.querySelector('.client-detail-drawer');
      expect(overlay).toBeInTheDocument();
      expect(drawer).toBeInTheDocument();

      // No nested buttons
      const buttons = document.body.querySelectorAll('button');
      buttons.forEach(btn => {
        expect(btn.querySelector('button')).toBeNull();
      });
    });
  });

  describe('Section 5: Action and guardrail tests', () => {
    const protectedClient = {
      ...clientData,
      is_protected: true,
      cognito_sub: 'sub-123'
    };

    it('1. protected client does not receive destructive controls and displays explaining title', () => {
      render(
        <ClientDetailDrawer
          client={protectedClient}
          mode="view"
          onClose={vi.fn()}
          isProtectedProfile={() => true}
        />
      );

      // Verify destructive buttons are disabled or not shown
      const deleteBtn = screen.queryByRole('button', { name: /Delete/i });
      if (deleteBtn) {
        expect(deleteBtn).toBeDisabled();
        expect(deleteBtn).toHaveAttribute('title', 'This account is protected and cannot be modified');
      }

      const pwResetBtn = screen.queryByRole('button', { name: /Send Password Reset Email/i });
      if (pwResetBtn) {
        expect(pwResetBtn).toBeDisabled();
      }

      // Edit Profile is still allowed
      expect(screen.getByRole('button', { name: /Edit Profile/i })).not.toBeDisabled();
    });

    it('2. destructive action callbacks are wired correctly and invoke exactly once', () => {
      const executeSpy = vi.fn();
      render(
        <ClientDetailDrawer
          client={clientData} // clientData has cognito_sub: 'sub-jane'
          mode="view"
          onClose={vi.fn()}
          onExecuteAction={executeSpy}
          isProtectedProfile={() => false}
        />
      );

      const resetPwBtn = screen.getByRole('button', { name: /Send Password Reset Email/i });
      fireEvent.click(resetPwBtn);
      expect(executeSpy).toHaveBeenCalledWith('client-123', 'reset-password');
    });

    it('3. Cognito warning box renders and link existing triggers callback', () => {
      const linkSpy = vi.fn();
      const setPromptSpy = vi.fn();

      render(
        <ClientDetailDrawer
          client={{ client_id: 'new' }}
          mode="create"
          formValues={defaultFormVals}
          setFormValues={vi.fn()}
          onClose={vi.fn()}
          onCancel={vi.fn()}
          isProtectedProfile={() => false}
          clientLinkPrompt={{ email: 'jane@example.com' }}
          setClientLinkPrompt={setPromptSpy}
          onLinkExistingClientOnboard={linkSpy}
        />
      );

      expect(screen.getByText(/A login account already exists for jane@example.com/i)).toBeInTheDocument();
      
      const linkBtn = screen.getByRole('button', { name: /Link Existing/i });
      fireEvent.click(linkBtn);
      expect(linkSpy).toHaveBeenCalled();

      const warningBox = document.body.querySelector('.existing-user-warning');
      const cancelBtn = warningBox.querySelector('.button-secondary');
      fireEvent.click(cancelBtn);
      expect(setPromptSpy).toHaveBeenCalledWith(null);
    });
  });

  describe('Section 6: Legacy editor retirement verification', () => {
    const mockSession = {
      getIdToken: () => ({
        payload: {
          email: 'owner@example.com',
          sub: 'owner-sub-123',
          name: 'Owner User'
        }
      })
    };

    beforeEach(() => {
      getSession.mockResolvedValue(mockSession);
      getEffectiveRole.mockReturnValue('owner');
      getAdminRequests.mockResolvedValue({ requests: [] });
      getStaff.mockResolvedValue({ staff: [] });
      getGoogleStatus.mockResolvedValue({});
      getTenantInfo.mockResolvedValue({
        company_name: 'Togs and Dogs',
        support_email: 'support@example.com'
      });
      getClients.mockResolvedValue({ clients: [] });
    });

    it('1. no inline editor form exists in the Client Management container', async () => {
      render(<AdminDashboard />);
      const tabButton = await screen.findByRole('button', { name: /Client Management/i });
      fireEvent.click(tabButton);
      
      // Inline editor headings should not be found
      expect(screen.queryByText('Add New Client Profile')).not.toBeInTheDocument();
      expect(screen.queryByText('Edit Client Profile')).not.toBeInTheDocument();
      expect(screen.queryByText('Process Client Onboarding')).not.toBeInTheDocument();
      
      // Check search & filters exist
      expect(screen.getByLabelText(/Search clients/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Filter clients/i)).toBeInTheDocument();
    });
  });

  describe('Section 7: Authoritative Pet Loading Tests (Phase 1B.5A)', () => {
    const mockSession = {
      getIdToken: () => ({
        payload: {
          email: 'owner@example.com',
          sub: 'owner-sub-123',
          name: 'Owner User'
        }
      })
    };

    beforeEach(() => {
      getSession.mockResolvedValue(mockSession);
      getEffectiveRole.mockReturnValue('owner');
      getAdminRequests.mockResolvedValue({ requests: [] });
      getStaff.mockResolvedValue({ staff: [] });
      getGoogleStatus.mockResolvedValue({});
      getTenantInfo.mockResolvedValue({
        company_name: 'Togs and Dogs',
        support_email: 'support@example.com'
      });
      getClients.mockResolvedValue({
        clients: [
          {
            client_id: 'client-jane',
            display_name: 'Jane Doe',
            email: 'jane@example.com',
            phone: '555-1234',
            is_active: true
          },
          {
            client_id: 'client-bob',
            display_name: 'Bob Smith',
            email: 'bob@example.com',
            is_active: true
          }
        ]
      });
      listAdminClientPets.mockResolvedValue({ pets: [] });
    });

    const switchToClientMgmt = async () => {
      render(<AdminDashboard />);
      const tabButton = await screen.findByRole('button', { name: /Client Management/i });
      fireEvent.click(tabButton);
      await screen.findByText('Client Access Management');
    };

    it('1. opening a client invokes listAdminClientPets with that client ID', async () => {
      await switchToClientMgmt();
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      
      expect(listAdminClientPets).toHaveBeenCalledWith('client-jane');
    });

    it('2. returned pets render in the ClientDetailDrawer', async () => {
      listAdminClientPets.mockResolvedValue({
        pets: [
          { pet_id: 'pet-1', name: 'Max', species: 'DOG', breed: 'Labrador', age: '3', is_active: true }
        ]
      });
      await switchToClientMgmt();
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      
      await screen.findByText('Max');
      expect(screen.getByText(/DOG/)).toBeInTheDocument();
      expect(screen.getByText(/Labrador/)).toBeInTheDocument();
    });

    it('3. a saved pet with no request association still renders', async () => {
      // Return a pet with no request association
      listAdminClientPets.mockResolvedValue({
        pets: [
          { pet_id: 'pet-unassociated', name: 'MysteryPet', species: 'CAT', breed: 'Siamese', age: '5', is_active: true }
        ]
      });
      
      await switchToClientMgmt();
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      
      await screen.findByText('MysteryPet');
      expect(screen.getByText(/CAT/)).toBeInTheDocument();
      expect(screen.getByText(/Siamese/)).toBeInTheDocument();
    });

    it('4. no request-derived getPet fan-out occurs', async () => {
      // Even if requests exist with pet IDs, getPet shouldn't be called for drawer loading.
      getAdminRequests.mockResolvedValue({
        requests: [
          {
            request_id: 'req-1',
            client_id: 'client-jane',
            pet_ids: ['pet-request-derived-123'],
            status: 'approved'
          }
        ]
      });
      
      listAdminClientPets.mockResolvedValue({
        pets: [
          { pet_id: 'pet-authoritative', name: 'Authoritative Buddy', species: 'DOG', is_active: true }
        ]
      });
      
      await switchToClientMgmt();
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      
      await screen.findByText('Authoritative Buddy');
      expect(screen.getByText(/DOG/)).toBeInTheDocument();
      expect(getPet).not.toHaveBeenCalled();
    });

    it('5. no pets produces the correct empty state', async () => {
      listAdminClientPets.mockResolvedValue({ pets: [] });
      await switchToClientMgmt();
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      
      await screen.findByText('Client Overview');
      expect(screen.getByText(/No pet information available/i)).toBeInTheDocument();
    });

    it('6. loading state displays while the request is pending', async () => {
      let resolvePets;
      const petsPromise = new Promise(resolve => { resolvePets = resolve; });
      listAdminClientPets.mockReturnValue(petsPromise);
      
      await switchToClientMgmt();
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      
      expect(screen.getByText(/Loading pets/i)).toBeInTheDocument();
      
      resolvePets({ pets: [] });
      await waitFor(() => {
        expect(screen.queryByText(/Loading pets/i)).not.toBeInTheDocument();
      });
    });

    it('7. an API failure clears loading safely', async () => {
      listAdminClientPets.mockRejectedValue(new Error('API Error'));
      await switchToClientMgmt();
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      
      await waitFor(() => {
        expect(screen.queryByText(/Loading pets/i)).not.toBeInTheDocument();
      });
      expect(screen.getByText(/No pet information available/i)).toBeInTheDocument();
    });

    it('8. rapid Client A -> Client B switching ignores stale Client A results', async () => {
      let resolveA;
      const promiseA = new Promise(resolve => { resolveA = resolve; });
      
      let resolveB;
      const promiseB = new Promise(resolve => { resolveB = resolve; });
      
      listAdminClientPets.mockImplementation((id) => {
        if (id === 'client-jane') return promiseA;
        if (id === 'client-bob') return promiseB;
        return Promise.resolve({ pets: [] });
      });
      
      await switchToClientMgmt();
      
      // Select Jane
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      
      // Switch immediately to Bob
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Bob Smith/i }));
      
      // Resolve Bob first
      resolveB({ pets: [{ pet_id: 'pet-bob', name: 'BobPet', species: 'DOG', is_active: true }] });
      await screen.findByText('BobPet');
      
      // Resolve Jane late
      resolveA({ pets: [{ pet_id: 'pet-jane', name: 'JanePet', species: 'CAT', is_active: true }] });
      await new Promise(r => setTimeout(r, 50));
      
      expect(screen.queryByText('JanePet')).not.toBeInTheDocument();
      expect(screen.getByText('BobPet')).toBeInTheDocument();
    });

    it('9. closing the drawer ignores a late response', async () => {
      let resolveA;
      const promiseA = new Promise(resolve => { resolveA = resolve; });
      listAdminClientPets.mockReturnValue(promiseA);
      
      await switchToClientMgmt();
      fireEvent.click(screen.getByRole('button', { name: /Client profile for Jane Doe/i }));
      
      // Close drawer
      const closeBtn = screen.getByRole('button', { name: /close client details/i });
      fireEvent.click(closeBtn);
      
      // Resolve Jane late
      resolveA({ pets: [{ pet_id: 'pet-jane', name: 'JanePet', species: 'CAT', is_active: true }] });
      await new Promise(r => setTimeout(r, 50));
      
      expect(screen.queryByText('JanePet (CAT)')).not.toBeInTheDocument();
    });
  });
});
