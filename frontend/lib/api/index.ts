import { createMockService } from "../mocks/service.ts";
import type { ReliefService, DemoService } from "../services/contracts.ts";

// Swap this adapter for a ReliefService implementation when contracts are agreed.
// Components and hooks depend on interfaces, never on fixture imports.
const local = createMockService();
export const reliefService: ReliefService = local;
export const demoService: DemoService = local;
