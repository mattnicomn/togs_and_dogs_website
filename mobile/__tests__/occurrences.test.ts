import { projectOccurrences } from '../src/utils/occurrences';

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
});
