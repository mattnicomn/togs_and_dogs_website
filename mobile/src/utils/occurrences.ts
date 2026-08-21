import { JobOccurrence, PetRequest } from '../types';

export interface MobileOccurrence extends JobOccurrence {
  legacy?: boolean;
  actionBlocked?: boolean;
}

export interface ActionJobResolution {
  jobId: string | null;
  error: string | null;
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

  if (request.occurrence_hydration_failed) {
    const dates = request.selected_dates?.length ? request.selected_dates : [''];
    const windows = request.visit_windows?.length ? request.visit_windows : [undefined];
    return sortOccurrences(dates.flatMap(date => windows.map(window => ({
      job_id: '', request_id: request.request_id, occurrence_date: date,
      occurrence_window: window, status: request.status, legacy: true, actionBlocked: true,
    }))));
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

export const resolveActionJobId = (
  request: PetRequest,
  occurrence?: MobileOccurrence | null,
  routeJobId?: string | null,
): ActionJobResolution => {
  if (occurrence?.request_id && occurrence.request_id !== request.request_id) {
    return { jobId: null, error: 'Visit details changed. Refresh before continuing.' };
  }
  if (occurrence && !occurrence.legacy) {
    if (!occurrence.job_id) return { jobId: null, error: 'Exact occurrence identity is unavailable. Refresh and retry.' };
    if (routeJobId && routeJobId !== occurrence.job_id) {
      return { jobId: null, error: 'Visit details changed. Refresh before continuing.' };
    }
    return { jobId: occurrence.job_id, error: null };
  }
  if (occurrence?.actionBlocked) return { jobId: null, error: 'Occurrence details are unavailable. Refresh before continuing.' };

  const ids = [request.job_id, ...(request.job_ids || [])].filter(Boolean) as string[];
  const unique = [...new Set(ids)];
  if (unique.length !== 1) return { jobId: null, error: 'An exact visit could not be identified safely. Refresh and retry.' };
  if (occurrence?.job_id && occurrence.job_id !== unique[0]) {
    return { jobId: null, error: 'Visit details changed. Refresh before continuing.' };
  }
  if (routeJobId && routeJobId !== unique[0]) return { jobId: null, error: 'Visit details changed. Refresh before continuing.' };
  return { jobId: unique[0], error: null };
};
