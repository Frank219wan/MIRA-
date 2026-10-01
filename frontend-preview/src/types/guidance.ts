export interface ARGuidance {
  polygon: [number, number][];
  standardRegion: { center: [number, number]; radius: [number, number] };
  region: string;
  directionVector: [number, number];
  intensity: string;
}
export interface PersonalizedAction {
  actionId: string;
  reference: { where: string; direction: string; product: string };
  personalized: { where: string; direction: string };
  product: string;
  goal: string;
  whyChanged: string;
  instructions: string;
  stopWhen: string;
  arGuidance?: ARGuidance;
  personalizationStatus?: "personalized" | "unsupported" | "not_applicable";
  matchDecision?: "strong_match" | "low_match" | "missing_capability" | "functional_conflict";
}
export type CoachIntent =
  "下一步" | "重复一下" | "这里对吗" | "我画重了怎么办" | "我没有这支刷子";
