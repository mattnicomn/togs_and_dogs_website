import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ClientProfileCard from '../src/components/ClientProfileCard';
import StaffProfileCard from '../src/components/StaffProfileCard';
import { vi, describe, it, expect } from 'vitest';

describe('ClientProfileCard Behavioral Tests', () => {
  const mockClient = {
    client_id: 'client-123',
    display_name: 'Jane Doe',
    email: 'jane@example.com',
    request_count: 3,
    auto_created: false,
    pet_names_summary: 'Fido, Spot',
    pet_breeds_summary: 'Beagle, Dalmation'
  };

  const setupClientCard = (props = {}) => {
    const openClientDetail = vi.fn();
    const isProtectedProfile = vi.fn().mockReturnValue(false);
    
    const utils = render(
      <ClientProfileCard
        client={mockClient}
        isSelected={false}
        openClientDetail={openClientDetail}
        isProtectedProfile={isProtectedProfile}
        {...props}
      />
    );
    return { ...utils, openClientDetail, isProtectedProfile };
  };

  it('1. clicking the native summary button opens the correct client', async () => {
    const user = userEvent.setup();
    const { openClientDetail } = setupClientCard();

    // The primary card activation area is the button with class card-summary-button-link
    const summaryBtn = screen.getByRole('button', { name: /Client profile for Jane Doe/i });
    await user.click(summaryBtn);

    expect(openClientDetail).toHaveBeenCalledTimes(1);
    expect(openClientDetail).toHaveBeenCalledWith(mockClient, expect.any(Object));
  });

  it('2. Enter activates the summary button', async () => {
    const user = userEvent.setup();
    const { openClientDetail } = setupClientCard();

    const summaryBtn = screen.getByRole('button', { name: /Client profile for Jane Doe/i });
    summaryBtn.focus();
    await user.keyboard('{Enter}');

    expect(openClientDetail).toHaveBeenCalledTimes(1);
  });

  it('3. Space activates the summary button', async () => {
    const user = userEvent.setup();
    const { openClientDetail } = setupClientCard();

    const summaryBtn = screen.getByRole('button', { name: /Client profile for Jane Doe/i });
    summaryBtn.focus();
    await user.keyboard(' '); // Space key

    expect(openClientDetail).toHaveBeenCalledTimes(1);
  });

  it('4. View Details opens the same client', async () => {
    const user = userEvent.setup();
    const { openClientDetail } = setupClientCard();

    const viewDetailsBtn = screen.getByRole('button', { name: /^View Details$/i });
    await user.click(viewDetailsBtn);

    expect(openClientDetail).toHaveBeenCalledTimes(1);
    expect(openClientDetail).toHaveBeenCalledWith(mockClient, expect.any(Object));
  });

  it('5. selected styling is represented correctly', () => {
    const { container } = setupClientCard({ isSelected: true });
    
    // Check that selected indicator exists
    expect(screen.getByText('Selected')).toBeInTheDocument();
    
    // Check outer card styling has "selected" class
    const outerDiv = container.firstChild;
    expect(outerDiv).toHaveClass('selected');
  });

  it('6. View Details is not nested inside the summary button', () => {
    const { container } = setupClientCard();
    
    const summaryBtn = container.querySelector('.card-summary-button-link');
    const viewDetailsBtn = screen.getByRole('button', { name: /^View Details$/i });

    // View Details should NOT be a child of summaryBtn
    expect(summaryBtn).not.toContainElement(viewDetailsBtn);
  });
});

describe('StaffProfileCard Behavioral Tests', () => {
  const mockStaff = {
    staff_id: 'staff-456',
    display_name: 'John Smith',
    role: 'staff',
    is_virtual: true,
    is_orphaned_identity: true,
    assignment_color: '#ff9800'
  };

  const setupStaffCard = (props = {}) => {
    const openStaffDetail = vi.fn();
    const isProtectedProfile = vi.fn().mockReturnValue(false);
    const isSelf = vi.fn().mockReturnValue(false);
    const getAccessStatus = vi.fn().mockReturnValue({ label: 'Login Active', class: 'status-active' });

    const utils = render(
      <StaffProfileCard
        staff={mockStaff}
        isSelected={false}
        openStaffDetail={openStaffDetail}
        isProtectedProfile={isProtectedProfile}
        isSelf={isSelf}
        getAccessStatus={getAccessStatus}
        {...props}
      />
    );
    return { ...utils, openStaffDetail, isProtectedProfile, isSelf, getAccessStatus };
  };

  it('7. clicking the summary button opens the correct staff profile', async () => {
    const user = userEvent.setup();
    const { openStaffDetail } = setupStaffCard();

    const summaryBtn = screen.getByRole('button', { name: /Staff profile for John Smith/i });
    await user.click(summaryBtn);

    expect(openStaffDetail).toHaveBeenCalledTimes(1);
    expect(openStaffDetail).toHaveBeenCalledWith(mockStaff, expect.any(Object));
  });

  it('8. Enter activates the summary button', async () => {
    const user = userEvent.setup();
    const { openStaffDetail } = setupStaffCard();

    const summaryBtn = screen.getByRole('button', { name: /Staff profile for John Smith/i });
    summaryBtn.focus();
    await user.keyboard('{Enter}');

    expect(openStaffDetail).toHaveBeenCalledTimes(1);
  });

  it('9. Space activates the summary button', async () => {
    const user = userEvent.setup();
    const { openStaffDetail } = setupStaffCard();

    const summaryBtn = screen.getByRole('button', { name: /Staff profile for John Smith/i });
    summaryBtn.focus();
    await user.keyboard(' ');

    expect(openStaffDetail).toHaveBeenCalledTimes(1);
  });

  it('10. View Details opens the same staff profile', async () => {
    const user = userEvent.setup();
    const { openStaffDetail } = setupStaffCard();

    const viewDetailsBtn = screen.getByRole('button', { name: /^View Details$/i });
    await user.click(viewDetailsBtn);

    expect(openStaffDetail).toHaveBeenCalledTimes(1);
    expect(openStaffDetail).toHaveBeenCalledWith(mockStaff, expect.any(Object));
  });

  it('11. protected, self, virtual, and orphaned indicators remain renderable', () => {
    const isProtectedProfile = vi.fn().mockReturnValue(true);
    const isSelf = vi.fn().mockReturnValue(true);

    setupStaffCard({ isProtectedProfile, isSelf });

    expect(screen.getByText('Protected Platform Admin')).toBeInTheDocument();
    expect(screen.getByText('(You)')).toBeInTheDocument();
    expect(screen.getByText('Login Only')).toBeInTheDocument();
    expect(screen.getByText('⚠️ Orphaned')).toBeInTheDocument();
  });

  it('12. View Details is not nested inside the summary button', () => {
    const { container } = setupStaffCard();
    
    const summaryBtn = container.querySelector('.card-summary-button-link');
    const viewDetailsBtn = screen.getByRole('button', { name: /^View Details$/i });

    expect(summaryBtn).not.toContainElement(viewDetailsBtn);
  });
});
