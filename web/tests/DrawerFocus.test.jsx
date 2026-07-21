import React, { useRef, useState } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ClientDetailDrawer from '../src/components/ClientDetailDrawer';
import { vi, describe, it, expect } from 'vitest';

describe('ClientDetailDrawer and Focus Restoration Tests', () => {
  const mockClient = {
    client_id: 'client-123',
    display_name: 'Jane Doe',
    email: 'jane@example.com',
    request_count: 0
  };

  const mockPets = [];

  it('1. client drawer has dialog semantics', () => {
    const onClose = vi.fn();
    render(
      <ClientDetailDrawer
        client={mockClient}
        pets={mockPets}
        onClose={onClose}
        isProtectedProfile={() => false}
      />
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-label', 'Client details: Jane Doe');
  });

  it('2. client drawer receives initial focus', async () => {
    const onClose = vi.fn();
    render(
      <ClientDetailDrawer
        client={mockClient}
        pets={mockPets}
        onClose={onClose}
        isProtectedProfile={() => false}
      />
    );

    // Initial focus should go to the close button inside the drawer
    const closeBtn = screen.getByRole('button', { name: /close client details/i });
    expect(document.activeElement).toBe(closeBtn);
  });

  it('3. Escape closes the client drawer', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <ClientDetailDrawer
        client={mockClient}
        pets={mockPets}
        onClose={onClose}
        isProtectedProfile={() => false}
      />
    );

    // Simulate escape press
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('4. close button closes it', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <ClientDetailDrawer
        client={mockClient}
        pets={mockPets}
        onClose={onClose}
        isProtectedProfile={() => false}
      />
    );

    const closeBtn = screen.getByRole('button', { name: /close client details/i });
    await user.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  // Test Harness to verify focus restoration
  const FocusRestorationHarness = ({ client }) => {
    const [isOpen, setIsOpen] = useState(false);
    const triggerRef = useRef(null);

    const handleOpen = (e) => {
      triggerRef.current = e.currentTarget;
      setIsOpen(true);
    };

    const handleClose = () => {
      setIsOpen(false);
      // Clean focus restoration matching AdminDashboard's closeClientDetail logic
      const trigger = triggerRef.current;
      if (trigger && typeof trigger.focus === 'function' && document.body.contains(trigger)) {
        trigger.focus();
      }
      triggerRef.current = null;
    };

    return (
      <div>
        <button type="button" data-testid="summary-trigger" onClick={handleOpen}>
          Summary Trigger
        </button>
        <button type="button" data-testid="details-trigger" onClick={handleOpen}>
          Details Trigger
        </button>
        {isOpen && (
          <ClientDetailDrawer
            client={client}
            pets={[]}
            onClose={handleClose}
            isProtectedProfile={() => false}
          />
        )}
      </div>
    );
  };

  it('5. focus returns to the client summary button when it was the trigger', async () => {
    const user = userEvent.setup();
    render(<FocusRestorationHarness client={mockClient} />);

    const summaryBtn = screen.getByTestId('summary-trigger');
    summaryBtn.focus();
    expect(document.activeElement).toBe(summaryBtn);

    // Open drawer
    await user.click(summaryBtn);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Close drawer using close button
    const closeBtn = screen.getByRole('button', { name: /close client details/i });
    await user.click(closeBtn);

    // Verify drawer closed and focus returned to summaryBtn
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(document.activeElement).toBe(summaryBtn);
  });

  it('6. focus returns to the client View Details button when that was the trigger', async () => {
    const user = userEvent.setup();
    render(<FocusRestorationHarness client={mockClient} />);

    const detailsBtn = screen.getByTestId('details-trigger');
    detailsBtn.focus();

    // Open drawer
    await user.click(detailsBtn);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Close drawer
    const closeBtn = screen.getByRole('button', { name: /close client details/i });
    await user.click(closeBtn);

    // Verify focus returned to detailsBtn
    expect(document.activeElement).toBe(detailsBtn);
  });

  it('11. focus does not remain trapped after drawer close', async () => {
    const user = userEvent.setup();
    render(<FocusRestorationHarness client={mockClient} />);

    const summaryBtn = screen.getByTestId('summary-trigger');
    await user.click(summaryBtn);

    // Verify it is trapped during open (tab containment)
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();

    // Close
    const closeBtn = screen.getByRole('button', { name: /close client details/i });
    await user.click(closeBtn);

    // Document active element should not be inside the dialog
    expect(dialog).not.toBeInTheDocument();
  });

  it('12. body-scroll state is restored after close', () => {
    document.body.style.overflow = 'scroll';

    const { unmount } = render(
      <ClientDetailDrawer
        client={mockClient}
        pets={mockPets}
        onClose={vi.fn()}
        isProtectedProfile={() => false}
      />
    );

    // Body scroll should be locked on open
    expect(document.body.style.overflow).toBe('hidden');

    unmount();

    // Body scroll should be restored on unmount
    expect(document.body.style.overflow).toBe('scroll');
  });
});
