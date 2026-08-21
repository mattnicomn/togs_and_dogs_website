import { JobOccurrence, PetRequest } from '../types';

export interface MobileOccurrence extends JobOccurrence {
  legacy?: boolean;
  actionBlocked?: boolean;
}

const windowRank: Record<string, number> = { MORNING: 0, MIDDAY: 1, EVENING: 2 };

export const sortOccurrences = (items: MobileOccurrence[]) => [...items].sort((a, b) =>
  (a.occurrence_date || '').localeCompare(b.occurrence_date || '') ||
  ((a.occurrence_index ?? Number.MAX_SAFE_INTEGER) - (b.occurrence_index ?? Number.MAX_SAFE_INTEGER)) ||
  ((windowRank[a.occurrence_window || ''] ?? 99) - (windowRank[b.occurrence_window || ''] ?? 99)) ||
  a.job_id.localeCompare(b.job_id)
);

export const projectOccurrences = (request: PetRequest): MobileOccurrence[] => {
  const authoritative = request.job_completion_summary?.jobs;
  if (Array.isArray(authoritative) && authoritative.length) {
    return sortOccurrences(authoritative.map(job => ({ ...job, request_id: job.request_id || request.request_id })));
  }

  const exactIds = [request.job_id, ...(request.job_ids || [])].filter(Boolean) as string[];
  const uniqueIds = [...new Set(exactIds)];
  if (uniqueIds.length === 1) {
    return [{
      job_id: uniqueIds[0], request_id: request.request_id,
      occurrence_date: request.selected_dates?.[0], status: request.status, legacy: true,
      worker_id: request.worker_id, worker_name: request.worker_name,
    }];
  }

  if (uniqueIds.length > 1) {
    return [{
      job_id: '', request_id: request.request_id,
      occurrence_date: request.selected_dates?.[0], status: request.status,
      legacy: true, actionBlocked: true,
    }];
  }
  return [];
};
