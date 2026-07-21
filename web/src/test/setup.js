import '@testing-library/jest-dom';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Automatically clean up React DOM tree after each test
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// Mock window.scrollTo since it's not implemented in JSDOM
if (typeof window !== 'undefined') {
  window.scrollTo = () => {};
}
