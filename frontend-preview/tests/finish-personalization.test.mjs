import test from "node:test";
import assert from "node:assert/strict";
import * as finish from "../src/services/finish.ts";
test("counts only changed backend parameters, not fallback or no-op rules", () => {
  assert.equal(typeof finish.summarizeAdjustments, "function");
  const action = {
    actionId: "one",
    personalizationSource: "backend-personalization",
    faceProfileSource: "mock",
    backendPersonalization: {
      original_parameters: { direction_angle_deg: 10, extension_factor: 1 },
      personalized_parameters: { direction_angle_deg: 13, extension_factor: 1 },
      adjustments: [
        { parameter: "direction_angle_deg" },
        { parameter: "direction_angle_deg" },
        { parameter: "extension_factor" },
      ],
    },
  };
  const result = finish.summarizeAdjustments([
    action,
    {
      ...action,
      actionId: "fallback",
      personalizationSource: "mock/standard-fallback",
    },
  ]);
  assert.equal(result.adjustmentCount, 1);
  assert.equal(result.adapted, true);
  assert.equal(result.exampleProfile, true);
  assert.equal(result.changes.length, 1);
  assert.equal(finish.summarizeAdjustments([]).adjustmentCount, 0);
});
