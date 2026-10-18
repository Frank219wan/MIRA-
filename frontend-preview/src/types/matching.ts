import type { Product } from "./product";
export interface MatchResult {
  actionId: string;
  status: "matched" | "partial" | "missing";
  bestMatch: Product | null;
  score: number | null;
  capabilityChecks: { label: string; passed: boolean }[];
  reason: string;
  difference: string;
  impact: string;
  missingCapability: string[];
  hardConstraints: string[];
}
