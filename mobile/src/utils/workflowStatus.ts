/**
 * W4 Option A — client-facing workflow-summary status presentation.
 *
 * A booking/request LIST card shows a *workflow-position summary* derived from the
 * request-list RequestStatus. It is NOT canonical commercial quote state. Canonical
 * quote state (SENT / ACCEPTED / DECLINED / NOT_REQUIRED) comes only from
 * `GET /client/quotes/{requestId}` on a surface that intentionally fetches it
 * (ClientRequestDetailScreen) — never from this list mapping.
 *
 * Invariants:
 *  - Raw RequestStatus enum strings (e.g. QUOTE_NEEDED / QUOTE_SENT / QUOTED) must
 *    never reach the user.
 *  - Quote-phase request statuses collapse to NEUTRAL, non-commercial wording: the
 *    list must not claim a quote was sent / is awaiting acceptance / accepted /
 *    declined / payment due / not required.
 *  - Known non-quote statuses keep sensible friendly labels.
 *  - Unknown / unexpected values fall back to neutral wording, never a raw enum.
 *
 * This is deliberately a small per-surface presentation helper (the shared contract
 * notes display labels are platform-specific); it does not introduce a second
 * parallel quote-state taxonomy.
 */

export interface WorkflowStatusPresentation {
  /** User-facing badge/summary label. Never a raw enum string. */
  label: string;
  /** Hex color for the status badge. */
  color: string;
}

// Neutral wording used for quote-phase statuses and unknown/default values.
// "In Review" is the smallest consistent neutral vocabulary already implied by the
// existing "Pending Review" tone; it makes no commercial quote claim.
const NEUTRAL_IN_REVIEW_LABEL = 'In Review';
const NEUTRAL_COLOR = '#f59e0b'; // same amber used for PENDING_REVIEW (non-commercial, in-progress)

/**
 * Quote-phase RequestStatus values (and legacy synonyms) that must NOT render as raw
 * enums and must NOT imply commercial quote state on a list card. They collapse to a
 * neutral "still being processed" summary; the client opens the detail screen for the
 * authoritative quote.
 */
const QUOTE_PHASE_STATUSES = new Set<string>([
  'QUOTE_NEEDED',
  'QUOTE_SENT',
  'QUOTED',
]);

/**
 * Known, non-quote workflow statuses with deterministic friendly labels + colors.
 *
 * These are REQUEST/workflow-position labels (customerVisible RequestStatus values),
 * NOT canonical commercial quote state. In particular DECLINED here means the REQUEST
 * workflow was declined (terminal/danger) — it is NOT "quote declined" / "client
 * declined quote" / a commercial-offer or payment state. Canonical quote DECLINED is a
 * separate concept shown only on the detail surface that fetches the quote endpoint.
 */
const KNOWN_STATUS_PRESENTATION: Record<string, WorkflowStatusPresentation> = {
  PENDING_REVIEW: { label: 'Pending Review', color: '#f59e0b' },
  NEEDS_REVIEW: { label: 'Pending Review', color: '#f59e0b' },
  READY_FOR_APPROVAL: { label: 'In Review', color: '#f59e0b' },
  APPROVED: { label: 'Approved', color: '#3b82f6' },
  BOOKED: { label: 'Approved', color: '#3b82f6' },
  ASSIGNED: { label: 'Scheduled', color: '#10b981' },
  JOB_CREATED: { label: 'Scheduled', color: '#10b981' },
  SCHEDULED: { label: 'Scheduled', color: '#10b981' },
  COMPLETED: { label: 'Completed', color: '#6b7280' },
  // Terminal request-workflow decline (danger). Request-oriented wording only.
  DECLINED: { label: 'Declined', color: '#ef4444' },
  CANCELLATION_REQUESTED: { label: 'Cancellation Pending', color: '#ef4444' },
  CANCELLATION_DENIED: { label: 'Cancellation Denied', color: '#ef4444' },
  CANCELLED: { label: 'Cancelled', color: '#ef4444' },
};

/**
 * Map a request-list RequestStatus to a client-facing workflow-summary presentation.
 *
 * Quote-phase statuses and unknown/missing values both return the neutral "In Review"
 * summary. This NEVER returns a raw enum string and NEVER synthesizes commercial quote
 * terminology from RequestStatus.
 */
export function getWorkflowStatusPresentation(
  status: string | null | undefined
): WorkflowStatusPresentation {
  const key = (status || '').toUpperCase();

  if (!key) {
    return { label: NEUTRAL_IN_REVIEW_LABEL, color: NEUTRAL_COLOR };
  }

  if (QUOTE_PHASE_STATUSES.has(key)) {
    return { label: NEUTRAL_IN_REVIEW_LABEL, color: NEUTRAL_COLOR };
  }

  if (Object.prototype.hasOwnProperty.call(KNOWN_STATUS_PRESENTATION, key)) {
    return KNOWN_STATUS_PRESENTATION[key];
  }

  // Unknown / unexpected / legacy value: neutral fallback, never a raw enum.
  return { label: NEUTRAL_IN_REVIEW_LABEL, color: NEUTRAL_COLOR };
}

/** Convenience: workflow-summary label only. */
export function getWorkflowStatusLabel(status: string | null | undefined): string {
  return getWorkflowStatusPresentation(status).label;
}
