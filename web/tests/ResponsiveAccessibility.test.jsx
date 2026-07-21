import React from 'react';
import { render, screen } from '@testing-library/react';
import ClientDetailDrawer from '../src/components/ClientDetailDrawer';
import ClientProfileCard from '../src/components/ClientProfileCard';
import StaffProfileCard from '../src/components/StaffProfileCard';
import { vi, describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Responsive and Accessibility Coverage', () => {
  const clientData = {
    client_id: 'client-1',
    display_name: 'Alex Rivera',
    email: 'alex@example.com',
    request_count: 2
  };

  const staffData = {
    staff_id: 'staff-1',
    display_name: 'Casey Morgan',
    role: 'staff'
  };

  it('1. client drawer uses expected modal/dialog semantics and markup sections', () => {
    const { container } = render(
      <ClientDetailDrawer
        client={clientData}
        pets={[]}
        onClose={vi.fn()}
        isProtectedProfile={() => false}
      />
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-label', 'Client details: Alex Rivera');

    // Header, content, and footer should be represented in the drawer markup
    const header = document.querySelector('.client-detail-drawer-header');
    const content = document.querySelector('.client-detail-drawer-content');
    const footer = document.querySelector('.client-detail-drawer-footer');

    expect(header).toBeInTheDocument();
    expect(content).toBeInTheDocument();
    expect(footer).toBeInTheDocument();
  });

  it('2. client and staff cards have descriptive accessible names', () => {
    render(
      <ClientProfileCard
        client={clientData}
        isSelected={false}
        openClientDetail={vi.fn()}
        isProtectedProfile={vi.fn().mockReturnValue(false)}
      />
    );

    const clientBtn = screen.getByRole('button', { name: /Client profile for Alex Rivera/i });
    expect(clientBtn).toBeInTheDocument();

    render(
      <StaffProfileCard
        staff={staffData}
        isSelected={false}
        openStaffDetail={vi.fn()}
        isProtectedProfile={vi.fn().mockReturnValue(false)}
        isSelf={vi.fn().mockReturnValue(false)}
        getAccessStatus={vi.fn().mockReturnValue({ label: 'Login Active', class: 'status-active' })}
      />
    );

    const staffBtn = screen.getByRole('button', { name: /Staff profile for Casey Morgan/i });
    expect(staffBtn).toBeInTheDocument();
  });

  it('3. no invalid nested-button markup exists in rendered DOM for either card', () => {
    const { container: clientContainer } = render(
      <ClientProfileCard
        client={clientData}
        isSelected={false}
        openClientDetail={vi.fn()}
        isProtectedProfile={vi.fn().mockReturnValue(false)}
      />
    );

    // Verify no buttons are descendants of other buttons
    const clientButtons = clientContainer.querySelectorAll('button');
    clientButtons.forEach(btn => {
      expect(btn.querySelector('button')).toBeNull();
    });

    const { container: staffContainer } = render(
      <StaffProfileCard
        staff={staffData}
        isSelected={false}
        openStaffDetail={vi.fn()}
        isProtectedProfile={vi.fn().mockReturnValue(false)}
        isSelf={vi.fn().mockReturnValue(false)}
        getAccessStatus={vi.fn().mockReturnValue({ label: 'Login Active', class: 'status-active' })}
      />
    );

    const staffButtons = staffContainer.querySelectorAll('button');
    staffButtons.forEach(btn => {
      expect(btn.querySelector('button')).toBeNull();
    });
  });

  it('4. reduced-motion rules remain present in CSS', () => {
    const cssPath = path.resolve(__dirname, '../src/Admin.css');
    const cssContent = fs.readFileSync(cssPath, 'utf8');
    
    // Check that prefers-reduced-motion media query is defined in Admin.css
    expect(cssContent).toContain('prefers-reduced-motion');
  });
});
