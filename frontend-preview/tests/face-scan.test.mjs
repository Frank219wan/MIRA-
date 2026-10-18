import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as face from "../src/services/face.ts";
import { request } from "../src/services/api/client.ts";
import { apiConfig } from "../src/lib/config.ts";
const values = new Map();
globalThis.sessionStorage = {
  getItem: (k) => values.get(k) ?? null,
  setItem: (k, v) => values.set(k, String(v)),
  removeItem: (k) => values.delete(k),
};
const profile = JSON.parse(
  readFileSync(new URL("./fixtures/face_profile_v0_3.json", import.meta.url)),
);
Object.assign(apiConfig, { demoMode: false, mockFallback: true });
test("API client sends multipart unchanged without JSON content type", async () => {
  const original = globalThis.fetch;
  const data = new FormData();
  data.append("images", new Blob(["frame"]), "frame.jpg");
  try {
    globalThis.fetch = async (_url, options) => {
      assert.equal(options.body, data);
      assert.equal(options.headers["Content-Type"], undefined);
      return Response.json({ ok: true });
    };
    await request("/face-scan", data);
  } finally {
    globalThis.fetch = original;
  }
});
test("scan stores only validated aggregate; failure clears old profile; revoked consent ignores late result", async () => {
  assert.equal(typeof face.scanFaceImages, "function");
  const original = globalThis.fetch;
  const images = [1, 2, 3].map(
    () => new Blob(["frame"], { type: "image/jpeg" }),
  );
  try {
    face.setFaceConsent(true);
    globalThis.fetch = async () =>
      Response.json({
        aggregated_face_profile: profile,
        valid_frame_count: 3,
        quality_information: { frames: [] },
      });
    await face.scanFaceImages(images);
    assert.deepEqual(face.getFaceProfileDTO(), profile);
    globalThis.fetch = async () =>
      Response.json({ error: { message: "No face" } }, { status: 400 });
    assert.equal(await face.scanFaceImages(images), null);
    assert.equal(face.getFaceProfileDTO(), undefined);
    globalThis.fetch = async () =>
      Response.json({ aggregated_face_profile: profile, valid_frame_count: 2 });
    assert.equal(await face.scanFaceImages(images), null);
    assert.equal(face.getFaceProfileDTO(), undefined);
    let resolve;
    globalThis.fetch = () => new Promise((r) => (resolve = r));
    const pending = face.scanFaceImages(images);
    face.setFaceConsent(false);
    resolve(
      Response.json({
        aggregated_face_profile: profile,
        valid_frame_count: 3,
        quality_information: { frames: [] },
      }),
    );
    await pending;
    assert.equal(face.getFaceProfileDTO(), undefined);
  } finally {
    globalThis.fetch = original;
    face.setFaceConsent(false);
  }
});

test("opted-in profile survives module reload, stays numeric and is cleared on revoke", async () => {
  face.setFaceConsent(true);
  face.setFaceProfileDTO(profile);
  assert.equal(typeof face.setRememberFaceProfile, "function");
  face.setRememberFaceProfile(true);
  const reloaded = await import("../src/services/face.ts?reload=1");
  assert.deepEqual(reloaded.getFaceProfileDTO(), profile);
  assert.ok(!JSON.stringify([...values]).includes("data:image"));
  reloaded.setFaceConsent(false);
  assert.equal(reloaded.getFaceProfileDTO(), undefined);
  assert.equal(values.has("mira-face-profile"), false);
});
