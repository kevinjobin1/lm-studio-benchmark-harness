/**
 * Vitest setup file for SSE event tests.
 *
 * Auto-registers setupTest/teardownTest lifecycle hooks via vitest's
 * setupFiles mechanism — no test file needs to call beforeEach/afterEach
 * explicitly.
 *
 * Add this file to the project's setupFiles in vitest config.
 */
import { beforeEach, afterEach } from "vitest";
import { setupTest, teardownTest } from "./test-helpers";

beforeEach(setupTest);
afterEach(teardownTest);
