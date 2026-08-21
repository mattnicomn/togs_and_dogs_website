import { projectOccurrences, resolveActionJobId } from '../src/utils/occurrences';

const parent = (jobs?: any[], extra: any = {}) => ({
  request_id: 'req', client_id: 'client', client_name: 'Client', pet_name: 'Pet', service_type: 'CHECK_IN',
  selected_dates: ['2026-09-01'], status: 'ASSIGNED', created_at: '2026-01-01',
  ...(jobs ? { job_completion_summary: { jobs } } : {}), ...extra,
});

describe('E3B authoritative occurrence projection', () => {
  it('maps six exact Check-In children without selected-date index inference', () => {
    const jobs = ['2026-09-02', '2026-09-01'].flatMap((date, di) =>
      ['EVENING', 'MORNING', 'MIDDAY'].map((window, wi) => ({
        job_id: `${di}-${wi}`, request_id: 'req', occurrence_date: date,
        occurrence_window: window, occurrence_index: di * 3 + wi, status: 'ASSIGNED',
      })));
    const result = projectOccurrences(parent(jobs, { selected_dates: ['wrong'], job_ids: ['wrong'] }) as any);
    expect(result).toHaveLength(6);
    expect(new Set(result.map(x => x.job_id)).size).toBe(6);
    expect(result.slice(0, 3).every(x => x.occurrence_date === '2026-09-01')).toBe(true);
    expect(result.map(x => x.job_id)).not.toContain('wrong');
  });

  it('orders Overnight children and preserves start/completion metadata', () => {
    const result = projectOccurrences(parent([
      { job_id: 'o2', request_id: 'req', occurrence_date: '2026-11-02', occurrence_end_date: '2026-11-03', occurrence_index: 2, status: 'COMPLETED', completed_at: 'done' },
      { job_id: 'o1', request_id: 'req', occurrence_date: '2026-11-01', occurrence_end_date: '2026-11-02', occurrence_index: 1, status: 'ASSIGNED', started_at: 'start' },
    ]) as any);
    expect(result.map(x => x.job_id)).toEqual(['o1', 'o2']);
    expect(result[0].started_at).toBe('start');
    expect(result[1].completed_at).toBe('done');
  });

  it('uses singular legacy identity and blocks ambiguous multi-child legacy identity', () => {
    expect(projectOccurrences(parent(undefined, { job_id: 'one' }) as any)[0]).toMatchObject({ job_id: 'one', legacy: true });
    expect(projectOccurrences(parent(undefined, { job_ids: ['a', 'b'] }) as any)[0]).toMatchObject({ job_id: '', actionBlocked: true });
  });

  it('keeps degraded parent dates/windows visible without guessed child IDs', () => {
    const result = projectOccurrences(parent(undefined, {
      occurrence_hydration_failed: true,
      selected_dates: ['2026-09-01', '2026-09-02'],
      visit_windows: ['MORNING', 'EVENING'],
      job_ids: ['guess-1', 'guess-2'],
    }) as any);
    expect(result).toHaveLength(4);
    expect(result.every(x => x.job_id === '' && x.actionBlocked)).toBe(true);
  });
});

describe('E3B.1 action identity resolution', () => {
  const req = parent(undefined, { job_id: 'legacy' }) as any;

  it('prefers authoritative occurrence identity and fails closed on route or parent mismatch', () => {
    const exact = { job_id: 'child', request_id: 'req', status: 'ASSIGNED' } as any;
    expect(resolveActionJobId(req, exact, null)).toEqual({ jobId: 'child', error: null });
    expect(resolveActionJobId(req, exact, 'other').jobId).toBeNull();
    expect(resolveActionJobId(req, { ...exact, request_id: 'other-request' }, 'child').jobId).toBeNull();
  });

  it('accepts one legacy identity and blocks ambiguous child sets', () => {
    expect(resolveActionJobId(req, null, null)).toEqual({ jobId: 'legacy', error: null });
    expect(resolveActionJobId(req, { job_id: 'other', request_id: 'req', status: 'ASSIGNED', legacy: true }, null).jobId).toBeNull();
    expect(resolveActionJobId(parent(undefined, { job_ids: ['a', 'b'] }) as any, null, null).jobId).toBeNull();
  });
});
