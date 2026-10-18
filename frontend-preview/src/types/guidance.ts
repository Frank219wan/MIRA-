import type { PersonalizedEngineActionDTO } from "../services/api/dto";
export interface ARGuidance {
  polygon: [number, number][];
  standardRegion: { center: [number, number]; radius: [number, number] };
  region: string;
  directionVector: [number, number];
  intensity: string;
}
export interface PersonalizedAction {
  actionId: string;
  faceProfileSource?: "scan" | "mock";
  adjustmentDetails?: { label: string; description: string; basis: string }[];
  personalizationSource?: "backend-personalization" | "mock/standard-fallback";
  backendPersonalization?: PersonalizedEngineActionDTO;
  parameterSource?: "frontend-demo-baseline";
  reference: { where: string; direction: string; product: string };
  personalized: { where: string; direction: string };
  product: string;
  productSource: "matched" | "generic";
  goal: string;
  whyChanged: string;
  instructions: string;
  stopWhen: string;
  arGuidance: ARGuidance;
}
export type CoachIntent =
  "下一步" | "重复一下" | "这里对吗" | "我画重了怎么办" | "我没有这支刷子";
