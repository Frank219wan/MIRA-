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
  product_name?: string | null;
  brand?: string | null;
  category?: string | null;
  shade_name?: string | null;
  color_attributes?: Record<string, string>;
  finish?: string | null;
  depth?: string | null;
  reflectivity?: string | null;
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
    decision?:
      | "strong_match"
      | "low_match"
      | "missing_capability"
      | "functional_conflict"
      | null;
    best_match?: BeautyKitProductDTO | null;
    match_score: number;
    reason?: string | null;
    difference?: string | null;
    impact?: string | null;
    satisfied_capabilities: string[];
    missing_capabilities: string[];
    functional_conflict?: string | null;
    substitution_candidates: {
      product_id: string;
      match_score: number;
      hard_constraint_failures: string[];
      difference: string;
    }[];
    provenance?: {
      matcher_version: string;
      rules_version: string;
      source_step_index: number;
      product_requirement: string;
      evaluated_product_ids: string[];
      pre_cap_score: number;
      hard_constraint_score_cap: number;
      hard_constraints: {
        constraint: string;
        expected: string[];
        actual: string[];
        passed: boolean;
      }[];
      score_components: {
        component: string;
        points_awarded: number;
        points_possible: number;
        evidence: string;
      }[];
    } | null;
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
  action_id?: `A${number}` | null;
  step_index: number;
  personalization_status: "personalized" | "unsupported" | "not_applicable";
  standard_action: ActionUnitDTO;
  cv_standard_action?: AdaptedCVActionDTO | null;
  match_result?: MatchingResultDTO["items"][number] | null;
  face_profile?: { profile_id: string; version: "0.3" } | null;
  cv_personalized_action?: PersonalizedActionWrapperDTO | null;
  where: string;
  how: string;
  why: string;
  stop_when: string;
  reference_parameters: Record<string, unknown>;
  personalized_parameters: Record<string, unknown>;
  applied_rules: string[];
  provenance: {
    request_id?: string | null;
    run_id: string;
    source_recipe_id: string;
    source_step_index: number;
    face_profile_version: "0.3";
    face_profile_id: string;
    matching_id?: string | null;
    product_id?: string | null;
    mapping_version?: string | null;
    applied_rules: string[];
    cv_adjustments: CVAdjustmentDTO[];
    explanation_generator_version: string;
    prompt_version: string;
    provider_name: string;
    model_name?: string | null;
    fallback_used: boolean;
  };
  fallback_status: "none" | "template_fallback" | "standard_action_fallback";
}

export interface MyTutorialResponseDTO {
  schema_version: "0.2";
  tutorial_id: string;
  recipe_id: string;
  steps: MyTutorialStepDTO[];
}

export interface MyTutorialRequestDTO {
  tutorial_id?: string;
  recipe: StandardRecipeDTO;
  beauty_kit: BeautyKitDTO;
  face_profile: FaceProfileDTO;
  face_profile_id: string;
  target_effect: "cat_eye";
}
