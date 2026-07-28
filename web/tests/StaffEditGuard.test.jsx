import React, { useState, useRef } from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

/**
 * Phase 1B.5C-C: Staff Management Edit Profile Double-Click Guard Tests
 *
 * Tests the two fixes:
 * 1. Edit-mode guard ref prevents form submission immediately after entering edit mode
 * 2. No-change detection prevents unnecessary PATCH and keeps the drawer open
 */
describe('Phase 1B.5C-C — Staff Edit Profile Guard', () => {
  let mockUpdateStaff;
  let mockShowNotification;

  beforeEach(() => {
    mockUpdateStaff = vi.fn().mockResolvedValue({ display_name: 'Test Staff' });
    mockShowNotification = vi.fn();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  /**
   * Harness that replicates the exact guard logic from AdminDashboard.jsx
   */
  const StaffEditGuardHarness = ({ onUpdateStaff, onNotify }) => {
    const [isEditMode, setIsEditMode] = useState(false);
    const [isDrawerOpen, setIsDrawerOpen] = useState(true);
    const [staffForm, setStaffForm] = useState({
      display_name: 'Test Staff',
      role: 'Staff',
      is_assignable: true,
      assignment_color: 'var(--staff-ryan)',
      phone: '',
      notes: ''
    });
    const initialFormValues = {
      display_name: 'Test Staff',
      role: 'Staff',
      is_assignable: true,
      assignment_color: 'var(--staff-ryan)',
      phone: '',
      notes: ''
    };
    const editModeGuardRef = useRef(false);
    const editingStaffId = 'staff-123';

    const handleSaveStaff = async (e) => {
      e.preventDefault();

      // Phase 1B.5C-C: Block form submission if edit mode was just activated
      if (editModeGuardRef.current) {
        return;
      }

      if (!staffForm.display_name.trim()) {
        onNotify("Display name is required", "error");
        return;
      }

      // Phase 1B.5C-C: No-change detection
      if (editingStaffId && initialFormValues) {
        const hasChanges = (
          staffForm.display_name !== initialFormValues.display_name ||
          staffForm.role !== initialFormValues.role ||
          staffForm.is_assignable !== initialFormValues.is_assignable ||
          staffForm.assignment_color !== initialFormValues.assignment_color ||
          staffForm.phone !== initialFormValues.phone ||
          staffForm.notes !== initialFormValues.notes
        );
        if (!hasChanges) {
          onNotify("No changes to save", "info");
          return;
        }
      }

      try {
        await onUpdateStaff(editingStaffId, staffForm);
        onNotify("Staff updated successfully", "success");
        setIsDrawerOpen(false);
        setIsEditMode(false);
      } catch (err) {
        onNotify(err.message || "Failed to save staff", "error");
      }
    };

    if (!isDrawerOpen) return <div data-testid="drawer-closed">Drawer Closed</div>;

    return (
      <div data-testid="drawer-open">
        <div data-testid="edit-mode">{isEditMode ? 'edit' : 'view'}</div>

        {!isEditMode ? (
          <div data-testid="view-footer">
            <button
              type="button"
              data-testid="edit-profile-btn"
              onClick={() => {
                editModeGuardRef.current = true;
                setIsEditMode(true);
                setTimeout(() => { editModeGuardRef.current = false; }, 300);
              }}
            >
              Edit Profile
            </button>
          </div>
        ) : (
          <div data-testid="edit-footer">
            <form id="test-staff-form" onSubmit={handleSaveStaff}>
              <input
                data-testid="display-name-input"
                type="text"
                value={staffForm.display_name}
                onChange={(e) => setStaffForm({ ...staffForm, display_name: e.target.value })}
              />
            </form>
            <button type="submit" form="test-staff-form" data-testid="save-btn">
              Save Changes
            </button>
          </div>
        )}
      </div>
    );
  };

  it('1. clicking Edit Profile once renders the edit form and does not call updateStaff', () => {
    render(
      <StaffEditGuardHarness onUpdateStaff={mockUpdateStaff} onNotify={mockShowNotification} />
    );

    // Initially in view mode
    expect(screen.getByTestId('edit-mode').textContent).toBe('view');
    expect(screen.getByTestId('edit-profile-btn')).toBeInTheDocument();

    // Click Edit Profile
    fireEvent.click(screen.getByTestId('edit-profile-btn'));

    // Should now be in edit mode with form visible
    expect(screen.getByTestId('edit-mode').textContent).toBe('edit');
    expect(screen.getByTestId('save-btn')).toBeInTheDocument();
    expect(screen.getByTestId('display-name-input')).toBeInTheDocument();

    // updateStaff should NOT have been called
    expect(mockUpdateStaff).not.toHaveBeenCalled();
    expect(mockShowNotification).not.toHaveBeenCalled();
  });

  it('2. rapid double-click on Edit Profile does not submit the form', () => {
    render(
      <StaffEditGuardHarness onUpdateStaff={mockUpdateStaff} onNotify={mockShowNotification} />
    );

    const editBtn = screen.getByTestId('edit-profile-btn');

    // Simulate rapid double-click: first click switches to edit mode
    fireEvent.click(editBtn);

    // Now in edit mode — the Save button exists
    expect(screen.getByTestId('edit-mode').textContent).toBe('edit');
    const saveBtn = screen.getByTestId('save-btn');

    // Simulate the second click landing on Save (within the guard window)
    fireEvent.click(saveBtn);

    // Guard should have blocked the submission
    expect(mockUpdateStaff).not.toHaveBeenCalled();
    // No notification either (the guard returns silently)
    expect(mockShowNotification).not.toHaveBeenCalled();
  });

  it('3. Save Changes with no changes shows "No changes to save" and does not call updateStaff', () => {
    render(
      <StaffEditGuardHarness onUpdateStaff={mockUpdateStaff} onNotify={mockShowNotification} />
    );

    // Enter edit mode
    fireEvent.click(screen.getByTestId('edit-profile-btn'));

    // Advance timers past the guard window
    act(() => { vi.advanceTimersByTime(400); });

    // Click Save without changing anything
    fireEvent.click(screen.getByTestId('save-btn'));

    // Should show "No changes to save" notification
    expect(mockShowNotification).toHaveBeenCalledWith("No changes to save", "info");

    // Should NOT call updateStaff
    expect(mockUpdateStaff).not.toHaveBeenCalled();

    // Drawer should still be open
    expect(screen.getByTestId('drawer-open')).toBeInTheDocument();
  });

  it('4. Save Changes after a field change calls updateStaff and closes drawer on success', async () => {
    vi.useRealTimers(); // This test needs real timers for async resolution

    render(
      <StaffEditGuardHarness onUpdateStaff={mockUpdateStaff} onNotify={mockShowNotification} />
    );

    // Enter edit mode
    fireEvent.click(screen.getByTestId('edit-profile-btn'));

    // Wait past guard (real 300ms)
    await new Promise(resolve => setTimeout(resolve, 350));

    // Change a field
    fireEvent.change(screen.getByTestId('display-name-input'), { target: { value: 'Updated Name' } });

    // Click Save
    fireEvent.click(screen.getByTestId('save-btn'));

    // Should call updateStaff
    await waitFor(() => {
      expect(mockUpdateStaff).toHaveBeenCalledWith('staff-123', expect.objectContaining({
        display_name: 'Updated Name'
      }));
    });

    // Should show success notification
    expect(mockShowNotification).toHaveBeenCalledWith("Staff updated successfully", "success");

    // Drawer should close
    await waitFor(() => {
      expect(screen.getByTestId('drawer-closed')).toBeInTheDocument();
    });
  });
});
