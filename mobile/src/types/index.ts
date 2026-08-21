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
