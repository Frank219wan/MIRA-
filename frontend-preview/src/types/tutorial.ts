export type ParsingStage =
  | "uploading"
  | "extracting_frames"
  | "segmenting_steps"
  | "understanding_products"
  | "understanding_actions"
  | "building_recipe"
  | "completed"
  | "failed";
export interface MakeupAction {
  id: string;
  order: number;
  name: string;
  area: string;
  goal: string;
  productRequirement: string;
  tool: string;
  motion: string;
  intensity: string;
  targetResult: string;
  startTime: number;
  endTime: number;
}
export interface TutorialInput {
  uploadId?: string;
  preset?: boolean;
  kind: "video" | "link" | "image" | "example";
  name: string;
}
