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
