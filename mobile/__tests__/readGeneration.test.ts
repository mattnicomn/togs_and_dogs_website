/**
 * OPS-3A.3D.2: faithful unit tests for the authoritative-read stale-response
 * generation primitive used by ClientRequestDetailScreen.
 *
 * These prove the EXACT ordering/staleness semantics that make a slow read unable to
 * overwrite a newer one: a later-started read supersedes an earlier token, and a
 * guarded apply refuses to commit when its token is stale — regardless of the ORDER in
 * which the reads "resolve" (modeled here by applying tokens out of order).
 */
import { createReadGeneration, applyIfCurrent } from '../src/utils/readGeneration';

describe('readGeneration — stale-response generation primitive (OPS-3A.3D.2)', () => {
  it('begin() returns monotonically increasing tokens', () => {
    const gen = createReadGeneration();
    const a = gen.begin();
    const b = gen.begin();
    const c = gen.begin();
    expect(a).toBe(1);
    expect(b).toBe(2);
    expect(c).toBe(3);
  });

  it('only the most recently started read is current', () => {
    const gen = createReadGeneration();
    const a = gen.begin();
    const b = gen.begin();
    expect(gen.isCurrent(a)).toBe(false); // superseded
    expect(gen.isCurrent(b)).toBe(true);  // latest
  });

  it('a later read supersedes an earlier one even when applied/resolved out of order', () => {
    // Model Race A/B: read A starts, read B starts later, B commits first, A resolves
    // AFTER B. The out-of-order "resolution" is modeled by calling applyIfCurrent for B
    // first, then for A — A must be refused.
    const gen = createReadGeneration();
    let committed: string | null = null;

    const tokenA = gen.begin(); // older read (e.g. a slow focus GET)
    const tokenB = gen.begin(); // newer read (e.g. mutation reconciliation)

    // B resolves first and commits.
    const bResult = applyIfCurrent(gen, tokenB, () => { committed = 'B'; return 'B'; });
    expect(bResult).toBe('B');
    expect(committed).toBe('B');

    // A resolves AFTER B — stale token, must be refused (no overwrite).
    const aResult = applyIfCurrent(gen, tokenA, () => { committed = 'A'; return 'A'; });
    expect(aResult).toBeUndefined();
    expect(committed).toBe('B'); // B's commit survives; stale A discarded
  });

  it('mutation-start invalidation: bumping the generation before a reconciliation read discards an in-flight older read', () => {
    // Models beginMutation() advancing the generation before the reconciliation GET:
    // the focus read (token N) is invalidated at mutation start (N+1), and the
    // reconciliation read (N+2) is the only one that may commit.
    const gen = createReadGeneration();
    const focusToken = gen.begin();   // N: focus GET in flight
    gen.begin();                      // N+1: beginMutation() invalidation bump
    const reconToken = gen.begin();   // N+2: reconciliation GET

    let committed: string | null = null;
    // Reconciliation commits.
    applyIfCurrent(gen, reconToken, () => { committed = 'ACCEPTED'; });
    expect(committed).toBe('ACCEPTED');
    // The older focus GET resolves afterward — refused.
    applyIfCurrent(gen, focusToken, () => { committed = 'STALE_SENT'; });
    expect(committed).toBe('ACCEPTED');
  });

  it('a stale read cannot apply a 404/error-style clear over a newer valid read', () => {
    // Models stale 404/error suppression: an older read's terminal (unavailable/error)
    // write is gated by the same token guard, so it cannot clear newer valid state.
    const gen = createReadGeneration();
    let state: 'valid' | 'unavailable' | 'error' = 'valid';

    const staleToken = gen.begin(); // older read
    gen.begin();                    // newer read already current (committed 'valid')

    // Stale read later resolves 404 -> would set 'unavailable', but is refused.
    applyIfCurrent(gen, staleToken, () => { state = 'unavailable'; });
    expect(state).toBe('valid');
    // Stale read later rejects 5xx -> would set 'error', but is refused.
    applyIfCurrent(gen, staleToken, () => { state = 'error'; });
    expect(state).toBe('valid');
  });

  it('current() reflects the latest generation', () => {
    const gen = createReadGeneration();
    expect(gen.current()).toBe(0);
    gen.begin();
    gen.begin();
    expect(gen.current()).toBe(2);
  });
});
