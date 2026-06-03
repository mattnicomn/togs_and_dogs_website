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
