// HTTP boundary types mirror backend-reference. Domain types remain UI-owned.
export interface ActionUnitDTO {
  step_index: number;
  area: string;
  goal: string;
  product_requirement: string;
  tool: string;
  motion: string;
  intensity: string;
  target_result: string;
  time_range_seconds?: [number, number] | null;
  confidence?: number | null;
}
export interface StandardRecipeDTO {
  schema_version: "1.0";
  recipe_id: string;
  title: string;
  source_media_path: string;
  action_units: ActionUnitDTO[];
}
export interface TutorialMediaInputDTO {
  media_path: string;
  media_kind: "video" | "frame_directory";
  recipe_id: string;
  title: string;
}
export interface BeautyKitProductDTO {
  product_id: string;
  name: string;
  capability_ids: string[];
}
export interface BeautyKitDTO {
  schema_version: string;
  kit_id: string;
  name: string;
  products: BeautyKitProductDTO[];
}
export interface MatchingResultDTO {
  schema_version: string;
  matching_id: string;
  recipe_id: string;
  beauty_kit_id: string;
  items: {
    step_index: number;
    status: "matched" | "unmatched" | "substitution_candidate";
    product_id?: string | null;
    capability_id?: string | null;
    note?: string | null;
  }[];
}
export interface FaceProfileDTO {
  version: "0.3";
  eye_geometry: {
    eye_tail_angle: Bilateral;
    eye_spacing_ratio: number;
    relative_eye_length: Bilateral;
    eye_width_height_ratio: Bilateral;
    brow_eye_ratio: Bilateral;
    lower_lid_space_ratio: Bilateral;
    inner_corner_angle: {
      left_deg: number;
      right_deg: number;
      mean_deg: number;
    };
  };
  symmetry: {
    eye_width: number;
    eye_height: number;
    eye_aspect_ratio: number;
    eye_tail_angle_difference: number;
  };
  raw_geometry_reference: Record<string, unknown>;
  confidence: {
    pose_normalized: boolean;
    expression_controlled: boolean;
  };
}
interface Bilateral {
  left: number;
  right: number;
  mean: number;
}
export interface CVAdaptationDTO {
  schema_version: string;
  recipe_id: string;
  face_profile: FaceProfileDTO;
}

export interface CVStandardMakeupActionDTO {
  action_id: `A${number}`;
  parameters: Record<string, unknown>;
}

export interface AdaptedCVActionDTO {
  mapping_version: "1.0";
  mapping_id: string;
  source_step_index: number;
  standard_makeup_action: CVStandardMakeupActionDTO;
}

export interface CVAdjustmentDTO {
  rule_ids: string[];
  feature_path: string;
  feature_value: number;
  parameter: string;
  operation: "add" | "multiply";
  adjustment_value: number;
  original_value: number;
  personalized_value: number;
}

export interface CVPersonalizedActionDTO {
  action_id: `A${number}`;
  original_parameters: Record<string, unknown>;
  personalized_parameters: Record<string, unknown>;
  applied_rules: string[];
  adjustments: CVAdjustmentDTO[];
}

export interface PersonalizedActionWrapperDTO {
  schema_version: "0.2";
  recipe_id: string;
  step_index: number;
  face_profile_version: "0.3";
  personalized_action: CVPersonalizedActionDTO;
  provenance: AdaptedCVActionDTO;
}

export interface MyTutorialStepDTO {
  step_index: number;
  standard_action: ActionUnitDTO;
  cv_standard_action?: AdaptedCVActionDTO | null;
  match_result?: MatchingResultDTO["items"][number] | null;
  face_profile?: { profile_id: string; version: "0.3" } | null;
  cv_personalized_action?: PersonalizedActionWrapperDTO | null;
  instructions: {
    where?: string | null;
    how?: string | null;
    why?: string | null;
    stop_when?: string | null;
  };
  provenance: Record<string, string>;
  fallback_status:
    | "none"
    | "standard_action"
    | "mapping_pending"
    | "profile_unavailable";
  ar_guidance_status: "pending_cv_contract";
}

export interface MyTutorialResponseDTO {
  schema_version: "0.2";
  tutorial_id: string;
  recipe_id: string;
  steps: MyTutorialStepDTO[];
}
