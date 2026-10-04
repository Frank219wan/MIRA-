import type { Product } from "./product";
export interface MatchResult {
  actionId: string;
  status: "matched" | "partial" | "missing";
  bestMatch: Product | null;
  score: number;
  capabilityChecks: { label: string; passed: boolean }[];
  difference: string;
  impact: string;
  missingCapability: string[];
}
