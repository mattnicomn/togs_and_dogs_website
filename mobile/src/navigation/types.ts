import { REQUEST_STATUSES } from '../contracts/generatedContracts';

type CanonicalRequestStatus = keyof typeof REQUEST_STATUSES.statuses;

export const REQUEST_LIST_FILTERS = {
  pendingReview: 'PENDING_REVIEW',
  approved: 'APPROVED',
  assigned: 'ASSIGNED',
  all: 'ALL',
  completed: 'COMPLETED',
  cancelled: 'CANCELLED',
} as const satisfies Record<string, CanonicalRequestStatus | 'ALL'>;

export type RequestListFilter = typeof REQUEST_LIST_FILTERS[keyof typeof REQUEST_LIST_FILTERS];

export type AdminTabParamList = {
  Dashboard: undefined;
  Requests: { initialFilter?: RequestListFilter } | undefined;
  Schedule: undefined;
};

/**
 * OPS-3A.3B: Client stack routes. The client detail screen is a durable shell
 * reached from the Bookings tab; it receives ONLY a requestId and fetches its
 * own authoritative data (never trusts a navigation-passed quote/request object).
 */
export type ClientStackParamList = {
  ClientTabs: undefined;
  IntakeScreen: undefined;
  ClientRequestDetail: { requestId: string };
};
