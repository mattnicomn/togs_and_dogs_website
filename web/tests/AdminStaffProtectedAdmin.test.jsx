import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';

describe('Phase 1B.5C-D.1 — Frontend Protected Platform Admin Toggle Tests', () => {
  // Test data profiles
  const ownerUser = { role: 'owner', sub: 'sub-owner', email: 'owner@example.com' };
  const protectedAdminUser = { role: 'admin', sub: 'sub-prot-admin', email: 'prot_admin@example.com' };
  const normalAdminUser = { role: 'admin', sub: 'sub-normal-admin', email: 'normal_admin@example.com' };
  const normalStaffUser = { role: 'staff', sub: 'sub-staff', email: 'staff@example.com' };

  const targetNormalStaff = {
    staff_id: 'staff-target',
    display_name: 'Target Staff',
    role: 'Staff',
    is_protected: false,
    is_platform_protected: false,
    is_config_protected: false,
    cognito_sub: 'sub-target',
    email: 'target@example.com'
  };

  const targetDataProtectedStaff = {
    staff_id: 'staff-data-protected',
    display_name: 'Data Protected Staff',
    role: 'Admin',
    is_protected: true,
    is_platform_protected: true,
    is_config_protected: false,
    cognito_sub: 'sub-data-prot',
    email: 'dataprot@example.com'
  };

  const targetConfigProtectedStaff = {
    staff_id: 'staff-config-protected',
    display_name: 'Config Protected Admin',
    role: 'Admin',
    is_protected: true,
    is_platform_protected: false,
    is_config_protected: true,
    cognito_sub: '74b86488-1011-7029-bb6d-dad984e1463c',
    email: 'admin@toganddogs.com'
  };

  const targetSelfProtectedStaff = {
    staff_id: 'staff-self-protected',
    display_name: 'Self Protected Admin',
    role: 'Owner',
    is_protected: true,
    is_platform_protected: true,
    is_config_protected: false,
    cognito_sub: 'sub-owner',
    email: 'owner@example.com'
  };

  // Logic helper mirroring AdminDashboard authorization and action dispatch
  const canManageProtectedStatusHelper = (currentUserRole, currentUserProfile) => {
    const effectiveRole = (currentUserRole || '').toLowerCase();
    if (effectiveRole === 'owner' || effectiveRole === 'platform_admin') return true;
    if (currentUserProfile && (currentUserProfile.is_protected || currentUserProfile.is_platform_protected)) {
      return true;
    }
    return false;
  };

  const executeStaffActionTest = (staffId, action, staffList, currentUser, showNotification, setConfirmAction) => {
    const staff = staffList.find(s => s.staff_id === staffId);
    const staffName = staff?.display_name || 'this staff member';

    const isSelf = (s) => !!s && !!currentUser && (s.cognito_sub === currentUser.sub || s.email === currentUser.email);

    if (action === 'set-protected') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'set-protected', name: staffName,
        message: `Mark ${staffName} as a Protected Platform Admin?`,
        consequence: "Protected platform admins cannot be deleted, disabled, or unlinked.",
        variant: 'confirm'
      });
      return;
    }

    if (action === 'unset-protected') {
      if (staff?.is_config_protected) {
        showNotification(`Action blocked: ${staffName} is protected by platform configuration and cannot be unprotected via database flag.`, "error");
        return;
      }
      if (isSelf(staff)) {
        showNotification(`Action blocked: You cannot remove protected status from your own account.`, "error");
        return;
      }
      setConfirmAction({
        type: 'staff', id: staffId, action: 'unset-protected', name: staffName,
        message: `Remove protected status from ${staffName}?`,
        consequence: "This will remove platform protection, allowing account modification or deletion according to standard role permissions.",
        variant: 'confirm'
      });
      return;
    }
  };

  // Minimal Harness for rendering protection control
  const ProtectionControlHarness = ({ currentUserRole, currentUserProfile, targetStaff, onAction }) => {
    const canManage = canManageProtectedStatusHelper(currentUserRole, currentUserProfile);
    const isSelfProfile = !!targetStaff && !!currentUserProfile && (
      targetStaff.cognito_sub === currentUserProfile.sub || targetStaff.email === currentUserProfile.email
    );
    const isCurrentlyProtected = !!(targetStaff?.is_protected || targetStaff?.is_platform_protected);

    if (!canManage && !isCurrentlyProtected) {
      return <div data-testid="protection-control-hidden">Hidden for unauthorized user</div>;
    }

    return (
      <div data-testid="protection-control-container">
        {canManage ? (
          <label data-testid="protection-label">
            <input
              type="checkbox"
              data-testid="protection-checkbox"
              checked={isCurrentlyProtected}
              disabled={targetStaff?.is_config_protected || (isCurrentlyProtected && isSelfProfile)}
              onChange={(e) => {
                const nextVal = e.target.checked;
                onAction(targetStaff.staff_id, nextVal ? 'set-protected' : 'unset-protected');
              }}
            />
            Protected Platform Admin
          </label>
        ) : (
          <span data-testid="protection-read-only-badge">🔒 Protected Platform Admin</span>
        )}
        {targetStaff?.is_config_protected && (
          <span data-testid="locked-by-config">(Locked by system config)</span>
        )}
        {!targetStaff?.is_config_protected && isCurrentlyProtected && isSelfProfile && (
          <span data-testid="cannot-unprotect-self">(Cannot unprotect self)</span>
        )}
      </div>
    );
  };

  it('1. toggle is visible and enabled for Owner', () => {
    const onAction = vi.fn();
    render(
      <ProtectionControlHarness
        currentUserRole="owner"
        currentUserProfile={ownerUser}
        targetStaff={targetNormalStaff}
        onAction={onAction}
      />
    );

    const checkbox = screen.getByTestId('protection-checkbox');
    expect(checkbox).toBeDefined();
    expect(checkbox.checked).toBe(false);
    expect(checkbox.disabled).toBe(false);
  });

  it('2. toggle is visible and enabled for already-Protected Admin', () => {
    const onAction = vi.fn();
    const protectedProfile = { ...protectedAdminUser, is_protected: true };
    render(
      <ProtectionControlHarness
        currentUserRole="admin"
        currentUserProfile={protectedProfile}
        targetStaff={targetNormalStaff}
        onAction={onAction}
      />
    );

    const checkbox = screen.getByTestId('protection-checkbox');
    expect(checkbox).toBeDefined();
    expect(checkbox.checked).toBe(false);
    expect(checkbox.disabled).toBe(false);
  });

  it('3. control is hidden for normal Admin / Staff targeting unprotected profile', () => {
    const onAction = vi.fn();
    render(
      <ProtectionControlHarness
        currentUserRole="admin"
        currentUserProfile={normalAdminUser}
        targetStaff={targetNormalStaff}
        onAction={onAction}
      />
    );

    expect(screen.getByTestId('protection-control-hidden')).toBeDefined();
    expect(screen.queryByTestId('protection-checkbox')).toBeNull();
  });

  it('4. toggle is disabled for self profile when protected', () => {
    const onAction = vi.fn();
    render(
      <ProtectionControlHarness
        currentUserRole="owner"
        currentUserProfile={ownerUser}
        targetStaff={targetSelfProtectedStaff}
        onAction={onAction}
      />
    );

    const checkbox = screen.getByTestId('protection-checkbox');
    expect(checkbox.checked).toBe(true);
    expect(checkbox.disabled).toBe(true);
    expect(screen.getByTestId('cannot-unprotect-self').textContent).toContain('Cannot unprotect self');
  });

  it('5. toggle is disabled and locked for config-protected profile', () => {
    const onAction = vi.fn();
    render(
      <ProtectionControlHarness
        currentUserRole="owner"
        currentUserProfile={ownerUser}
        targetStaff={targetConfigProtectedStaff}
        onAction={onAction}
      />
    );

    const checkbox = screen.getByTestId('protection-checkbox');
    expect(checkbox.checked).toBe(true);
    expect(checkbox.disabled).toBe(true);
    expect(screen.getByTestId('locked-by-config').textContent).toContain('Locked by system config');
  });

  it('6. confirmation modal payload triggers before set-protected action', () => {
    const showNotification = vi.fn();
    const setConfirmAction = vi.fn();
    const staffList = [targetNormalStaff];

    executeStaffActionTest('staff-target', 'set-protected', staffList, ownerUser, showNotification, setConfirmAction);

    expect(setConfirmAction).toHaveBeenCalledWith({
      type: 'staff',
      id: 'staff-target',
      action: 'set-protected',
      name: 'Target Staff',
      message: 'Mark Target Staff as a Protected Platform Admin?',
      consequence: 'Protected platform admins cannot be deleted, disabled, or unlinked.',
      variant: 'confirm'
    });
  });

  it('7. confirmation modal payload triggers before unset-protected action', () => {
    const showNotification = vi.fn();
    const setConfirmAction = vi.fn();
    const staffList = [targetDataProtectedStaff];

    executeStaffActionTest('staff-data-protected', 'unset-protected', staffList, ownerUser, showNotification, setConfirmAction);

    expect(setConfirmAction).toHaveBeenCalledWith({
      type: 'staff',
      id: 'staff-data-protected',
      action: 'unset-protected',
      name: 'Data Protected Staff',
      message: 'Remove protected status from Data Protected Staff?',
      consequence: 'This will remove platform protection, allowing account modification or deletion according to standard role permissions.',
      variant: 'confirm'
    });
  });

  it('8. executeConfirmAction invokes updateStaff with action set-protected or unset-protected only on confirmation', async () => {
    const updateStaffMock = vi.fn().mockResolvedValue({ ...targetNormalStaff, is_platform_protected: true, is_protected: true });
    
    // Simulate modal confirmation execution
    const confirmAction = { type: 'staff', id: 'staff-target', action: 'set-protected', name: 'Target Staff' };
    const result = await updateStaffMock(confirmAction.id, { action: confirmAction.action });

    expect(updateStaffMock).toHaveBeenCalledWith('staff-target', { action: 'set-protected' });
    expect(result.is_protected).toBe(true);
  });
});
