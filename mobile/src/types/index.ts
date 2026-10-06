export interface PetRequest {
  request_id: string;
  client_id: string;
  client_name: string;
  pet_name: string;
  service_type: string;
  selected_dates: string[];
  status: string;
  created_at: string;
  special_instructions?: string;
  address?: string;
  phone?: string;
  preferred_sitter?: string;
  timeframe?: string;
  worker_name?: string;
  assigned_sitter?: string;
  worker_id?: string;
  assigned_sitter_id?: string;
  job_id?: string;
  job_ids?: string[];
  completed_job_ids?: string[];
  payment_status?: string;
  job_completion_summary?: { jobs?: JobOccurrence[] };
  visit_windows?: string[];
  occurrence_hydration_failed?: boolean;
}

export interface JobOccurrence {
  job_id: string;
  request_id: string;
  occurrence_date?: string;
  occurrence_end_date?: string;
  occurrence_window?: string;
  occurrence_index?: number;
  total_occurrences?: number;
  status: string;
  worker_id?: string;
  worker_name?: string;
  start_time?: string;
  end_time?: string;
  started_at?: string;
  started_by?: string;
  completed_at?: string;
  completed_by?: string;
  visit_notes?: string;
}

/**
 * OPS-3A.3A: Client-safe quote projection returned by GET /client/quotes/{requestId}.
 *
 * Mirrors the backend hard-allowlist projection (build_client_quote_projection /
 * CLIENT_QUOTE_ALLOWLIST). Only client-safe fields are modeled here — internal/
 * admin quote fields (quote_notes_internal, quote_history, audit_log, Stripe ids,
 * etc.) are deliberately absent, as are quote_declined_revision /
 * quote_declined_reason_client (not emitted to clients).
 *
 * Nullability reflects actual API behavior: the allowlist always emits these keys,
 * but values can be null when the underlying record has not set them (e.g. no
 * acceptance timestamp before acceptance, no client notes).
 *
 * quote_status is one of: NOT_REQUIRED | DRAFT | SENT | ACCEPTED | DECLINED | SUPERSEDED.
 */
export interface ClientQuote {
  request_id: string;
  quote_status: string;
  quote_revision: number;
  quote_amount_cents: number;
  currency: string;
  deposit_amount_cents: number;
  payment_requirement: string;
  payment_status: string | null;
  payment_required: boolean;
  quote_notes_client: string | null;
  quote_sent_at: string | null;
  quote_accepted_at: string | null;
  quote_accepted_revision: number | null;
  // Client-safe booking/request context (from the REQUEST record).
  service_type: string | null;
  pet_names: string[] | null;
  selected_dates: string[] | null;
  start_date: string | null;
  end_date: string | null;
}

/**
 * OPS-3A.3A: Response of POST /client/quotes/{requestId}/accept.
 *
 * Includes the read-only booking-readiness echo (booking_ready / booking_ready_reason)
 * which is NOT part of the GET projection — it is computed per-accept and never
 * persists an APPROVED booking. payment_requirement/payment_status are informational.
 */
export interface ClientQuoteAcceptResponse {
  message: string;
  request_id: string;
  quote_status: string;
  quote_revision: number;
  quote_accepted_revision: number | null;
  quote_accepted_at: string | null;
  booking_ready: boolean;
  booking_ready_reason: string | null;
  payment_requirement: string | null;
  payment_status: string | null;
}

/**
 * OPS-3A.3A: Response of POST /client/quotes/{requestId}/decline.
 *
 * quote_declined_reason_client is echoed only when a reason was submitted; the
 * client UI (Decision 4) does not re-display it after a successful decline.
 */
export interface ClientQuoteDeclineResponse {
  message: string;
  request_id: string;
  quote_status: string;
  quote_revision: number;
  quote_declined_at: string | null;
  quote_declined_reason_client?: string;
}

export interface Staff {
  staff_id: string;
  name: string;
  display_name?: string;
  email: string;
  role: string;
  status: string;
  is_active?: boolean;
  is_assignable?: boolean;
}

export interface Client {
  client_id: string;
  name: string;
  email: string;
  phone: string;
  status: string;
}
