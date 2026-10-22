/**
 * W4 Option A — workflow-summary status mapping regression tests.
 *
 * Proves raw RequestStatus enums never leak, quote-phase statuses collapse to neutral
 * non-commercial wording, known non-quote statuses keep friendly labels, and unknown
 * values fall back to neutral wording (never a raw enum). No commercial quote state is
 * synthesized from RequestStatus.
 */
import {
  getWorkflowStatusPresentation,
  getWorkflowStatusLabel,
} from '../src/utils/workflowStatus';

const NEUTRAL = 'In Review';

// Any wording that would imply canonical commercial quote state on a list card.
const COMMERCIAL_CLAIM = /quote|accepted|declined|payment|deposit|not required|awaiting/i;

describe('getWorkflowStatusPresentation — quote-phase collapses to neutral', () => {
  it.each(['QUOTE_NEEDED', 'QUOTE_SENT', 'QUOTED'])(
    '%s does not render raw and maps to neutral workflow wording',
    (status) => {
      const { label } = getWorkflowStatusPresentation(status);
      expect(label).toBe(NEUTRAL);
      expect(label).not.toBe(status);
      expect(label).not.toMatch(/QUOTE/);
      // No commercial quote claim is synthesized from RequestStatus.
      expect(label).not.toMatch(COMMERCIAL_CLAIM);
    }
  );

  it('lowercase quote-phase values are handled consistently', () => {
    expect(getWorkflowStatusLabel('quote_sent')).toBe(NEUTRAL);
  });
});

describe('getWorkflowStatusPresentation — known non-quote statuses', () => {
  it.each([
    ['PENDING_REVIEW', 'Pending Review'],
    ['APPROVED', 'Approved'],
    ['ASSIGNED', 'Scheduled'],
    ['JOB_CREATED', 'Scheduled'],
    ['COMPLETED', 'Completed'],
    ['CANCELLED', 'Cancelled'],
    ['DECLINED', 'Declined'],
    ['CANCELLATION_REQUESTED', 'Cancellation Pending'],
    ['CANCELLATION_DENIED', 'Cancellation Denied'],
  ])('%s maps to friendly label %s', (status, expected) => {
    expect(getWorkflowStatusLabel(status)).toBe(expected);
  });
});

describe('getWorkflowStatusPresentation — DECLINED is a terminal REQUEST decline, not a quote/unknown', () => {
  it('DECLINED renders "Declined" (not the neutral "In Review" fallback)', () => {
    const { label } = getWorkflowStatusPresentation('DECLINED');
    expect(label).toBe('Declined');
    expect(label).not.toBe(NEUTRAL);
  });

  it('DECLINED does not introduce quote/commercial terminology', () => {
    const { label } = getWorkflowStatusPresentation('DECLINED');
    // "Declined" is the legitimate REQUEST-workflow label. It must not carry commercial
    // quote/payment phrasing ("quote", "payment", "deposit", "accepted", "awaiting",
    // "not required"). The bare word "declined" as a request status is acceptable; the
    // assertion targets commercial terminology specifically.
    expect(label).not.toMatch(/quote|accepted|payment|deposit|not required|awaiting/i);
    expect(label).toBe('Declined');
  });

  it('DECLINED uses a danger-style color consistent with CANCELLED', () => {
    expect(getWorkflowStatusPresentation('DECLINED').color).toBe(
      getWorkflowStatusPresentation('CANCELLED').color
    );
  });
});

describe('getWorkflowStatusPresentation — unknown / missing fall back neutral', () => {
  it.each(['SOME_FUTURE_STATUS', 'WEIRD_ENUM', '', undefined, null])(
    'value %p does not leak a raw enum and uses neutral wording',
    (status) => {
      const { label } = getWorkflowStatusPresentation(status as any);
      expect(label).toBe(NEUTRAL);
      if (typeof status === 'string' && status) {
        expect(label).not.toBe(status);
      }
    }
  );

  it('an unknown value never contains underscores (no raw enum text)', () => {
    expect(getWorkflowStatusLabel('SOME_FUTURE_STATUS')).not.toMatch(/_/);
  });
});

describe('getWorkflowStatusPresentation — always returns a color + non-empty label', () => {
  it.each(['QUOTE_SENT', 'APPROVED', 'UNKNOWN_X', ''])('value %p', (status) => {
    const { label, color } = getWorkflowStatusPresentation(status as any);
    expect(label.length).toBeGreaterThan(0);
    expect(color).toMatch(/^#[0-9a-f]{6}$/i);
  });
});
