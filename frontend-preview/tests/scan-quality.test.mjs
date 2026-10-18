import test from "node:test";
import assert from "node:assert/strict";
import { pixelIssue, faceIssue } from "../src/services/scanQuality.ts";
test("reject low resolution, dark, overexposed and detail-free inputs", () => {
  const flat = (v) => new Uint8ClampedArray(400).fill(v);
  assert.match(pixelIssue(100, 100, flat(100)), /分辨率/);
  assert.match(pixelIssue(640, 480, flat(0)), /过暗/);
  assert.match(pixelIssue(640, 480, flat(255)), /过亮/);
  assert.match(pixelIssue(640, 480, flat(100)), /清晰/);
});
test("reject no face, multiple faces, incomplete geometry without claiming occlusion diagnosis", () => {
  assert.match(faceIssue([]), /未能识别/);
  assert.match(faceIssue([[], []]), /多张/);
  assert.match(faceIssue([[]]), /不完整/);
});

test("motion guard rejects drift, zoom and rotation while tolerating tiny jitter", async () => {
  const { motionIssue } = await import("../src/services/scanQuality.ts");
  assert.equal(typeof motionIssue, "function");
  const face = Array.from({ length: 468 }, () => ({ x: 0.5, y: 0.5, z: 0 }));
  face[33] = { x: 0.35, y: 0.45, z: 0 };
  face[263] = { x: 0.65, y: 0.45, z: 0 };
  assert.equal(
    motionIssue(
      face,
      face.map((p) => ({ ...p, x: p.x + 0.04 })),
    ),
    null,
  );
  assert.match(
    motionIssue(
      face,
      face.map((p) => ({ ...p, x: p.x + 0.075 })),
    ),
    /移动/,
  );
  assert.match(
    motionIssue(
      face,
      face.map((p) => ({ ...p, x: 0.5 + (p.x - 0.5) * 1.25 })),
    ),
    /移动/,
  );
  const rotated = face.map((p) => ({ ...p }));
  rotated[263].y += 0.08;
  assert.match(motionIssue(face, rotated), /移动/);
});

test("brief blink recovers, sustained movement still fails", async () => {
  const { tolerateBriefScanChange } =
    await import("../src/services/scanQuality.ts");
  let n = 0;
  assert.equal(
    await tolerateBriefScanChange(async () => {
      if (n++ < 2) throw new Error("无法清楚识别睁开的双眼");
      return "ready";
    }),
    "ready",
  );
  let attempts = 0;
  await assert.rejects(
    tolerateBriefScanChange(async () => {
      attempts++;
      throw new Error("面部移动");
    }),
    /移动/,
  );
  assert.equal(attempts, 5);
});
