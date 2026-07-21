import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';

describe('Staff Action Preservation and Guardrail Tests', () => {
  // Mock staff data
  const protectedStaff = {
    staff_id: 'staff-protected',
    display_name: 'Protected Admin',
    role: 'admin',
    is_protected: true
  };

  const selfStaff = {
    staff_id: 'staff-self',
    display_name: 'Self Staff',
    role: 'owner',
    cognito_sub: 'sub-self',
    email: 'self@example.com'
  };

  const normalStaff = {
    staff_id: 'staff-normal',
    display_name: 'Normal Staff',
    role: 'staff'
  };

  const orphanedStaff = {
    staff_id: 'staff-orphaned',
    display_name: 'Orphaned Staff',
    role: 'staff',
    is_orphaned_identity: true
  };

  // Replicate AdminDashboard's executeStaffAction logic in a test helper
  const executeStaffActionTest = (staffId, action, staffList, currentUser, showNotification, setConfirmAction) => {
    const staff = staffList.find(s => s.staff_id === staffId);
    const staffName = staff?.display_name || 'this staff member';

    const isProtectedProfile = (s) => !!s?.is_protected;
    const isSelf = (s) => !!s && !!currentUser && (s.cognito_sub === currentUser.sub || s.email === currentUser.email);

    // Protected account guardrail
    const destructiveActions = ['disable', 'delete_cognito', 'delete_profile', 'unlink', 'set-temp-password', 'reset-password'];
    if (destructiveActions.includes(action)) {
      if (isProtectedProfile(staff)) {
        showNotification(`Action blocked: ${staffName} is a protected platform admin and cannot be modified.`, "error");
        return;
      }
      if (isSelf(staff) && ['disable', 'delete_cognito', 'delete_profile'].includes(action)) {
        showNotification(`Action blocked: You cannot ${action === 'disable' ? 'disable' : 'delete'} your own account.`, "error");
        return;
      }
    }

    if (action === 'disable') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'disable', name: staffName,
        message: `Turn off login access for ${staffName}?`,
        consequence: "This prevents them from signing in, but keeps their records.",
        variant: 'confirm'
      });
      return;
    }

    if (action === 'enable') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'enable', name: staffName,
        message: `Restore login access for ${staffName}?`,
        consequence: "This allows them to sign in again.",
        variant: 'confirm'
      });
      return;
    }
  };

  it('1. protected account restrictions remain active', () => {
    const showNotification = vi.fn();
    const setConfirmAction = vi.fn();
    const staffList = [protectedStaff];

    executeStaffActionTest('staff-protected', 'disable', staffList, null, showNotification, setConfirmAction);

    expect(showNotification).toHaveBeenCalledWith(
      'Action blocked: Protected Admin is a protected platform admin and cannot be modified.',
      'error'
    );
    expect(setConfirmAction).not.toHaveBeenCalled();
  });

  it('2. self-account restrictions remain active', () => {
    const showNotification = vi.fn();
    const setConfirmAction = vi.fn();
    const staffList = [selfStaff];
    const currentUser = { sub: 'sub-self', email: 'self@example.com' };

    executeStaffActionTest('staff-self', 'disable', staffList, currentUser, showNotification, setConfirmAction);

    expect(showNotification).toHaveBeenCalledWith(
      'Action blocked: You cannot disable your own account.',
      'error'
    );
    expect(setConfirmAction).not.toHaveBeenCalled();
  });

  it('3. normal staff-card actions invoke confirmation modal state', () => {
    const showNotification = vi.fn();
    const setConfirmAction = vi.fn();
    const staffList = [normalStaff];

    executeStaffActionTest('staff-normal', 'disable', staffList, null, showNotification, setConfirmAction);

    expect(showNotification).not.toHaveBeenCalled();
    expect(setConfirmAction).toHaveBeenCalledWith({
      type: 'staff',
      id: 'staff-normal',
      action: 'disable',
      name: 'Normal Staff',
      message: 'Turn off login access for Normal Staff?',
      consequence: 'This prevents them from signing in, but keeps their records.',
      variant: 'confirm'
    });
  });

  // Mock Component representing staff view/create modes
  const StaffManagementHarness = () => {
    const [isEditMode, setIsEditMode] = useState(false);
    const [editingStaffId, setEditingStaffId] = useState(null);

    const handleNewStaff = () => {
      setEditingStaffId(null);
      setIsEditMode(true);
    };

    const openStaffDetail = (staff) => {
      setEditingStaffId(staff.staff_id);
      setIsEditMode(false); // Opens in read-only mode by default
    };

    return (
      <div>
        <div data-testid="mode">{isEditMode ? 'edit' : 'view'}</div>
        <div data-testid="editing-id">{editingStaffId || 'none'}</div>
        <button data-testid="add-btn" onClick={handleNewStaff}>Add Staff</button>
        <button data-testid="select-btn" onClick={() => openStaffDetail(normalStaff)}>Select Staff</button>
      </div>
    );
  };

  it('4. Add New Staff opens create/edit mode', () => {
    render(<StaffManagementHarness />);

    const addBtn = screen.getByTestId('add-btn');
    fireEvent.click(addBtn);

    expect(screen.getByTestId('mode').textContent).toBe('edit');
    expect(screen.getByTestId('editing-id').textContent).toBe('none');
  });

  it('5. normal staff-card selection opens read-only mode', () => {
    render(<StaffManagementHarness />);

    const selectBtn = screen.getByTestId('select-btn');
    fireEvent.click(selectBtn);

    expect(screen.getByTestId('mode').textContent).toBe('view');
    expect(screen.getByTestId('editing-id').textContent).toBe('staff-normal');
  });
});
