// Vitest exposes `vi`, but this suite was written for Jest and calls
// `jest.fn()` in a few places. Alias it once here rather than rewriting
// every assertion.
import { vi } from 'vitest';

globalThis.jest = vi;
