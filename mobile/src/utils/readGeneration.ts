/**
 * OPS-3A.3D.2: pure stale-response generation primitive.
 *
 * Extracted (behavior-identical) from ClientRequestDetailScreen's authoritative-read
 * guard so the exact ordering/staleness logic can be unit-tested faithfully: begin a
 * read to get a monotonically increasing token, and only the latest token is current.
 * The component composes `isCurrent(token)` with its own `mountedRef` check and uses
 * `begin()` for every authoritative read (initial/focus/retry fetch, mutation/409/
 * ambiguous reconciliation) and for mutation-start invalidation.
 *
 * Pure and framework-free: no React, no I/O.
 */
export interface ReadGeneration {
  /** Start a new authoritative read; returns its monotonically increasing token. */
  begin(): number;
  /** True only if `token` is the most recently started read (not superseded). */
  isCurrent(token: number): boolean;
  /** Current generation value (for assertions/diagnostics). */
  current(): number;
}

export function createReadGeneration(): ReadGeneration {
  let generation = 0;
  return {
    begin: () => ++generation,
    isCurrent: (token: number) => token === generation,
    current: () => generation,
  };
}

/**
 * Apply a state write ONLY when `token` is still the current read; otherwise skip it.
 * Mirrors the component's guarded writes: a superseded (stale) read must never commit
 * its result over a newer read. Returns the apply() result when applied, else undefined.
 */
export function applyIfCurrent<T>(
  gen: ReadGeneration,
  token: number,
  apply: () => T,
): T | undefined {
  return gen.isCurrent(token) ? apply() : undefined;
}
