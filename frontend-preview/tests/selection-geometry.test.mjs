import test from "node:test";
import assert from "node:assert/strict";
import {
  convexHull,
  displayPointToRaw,
  isSimplePolygon,
  pointInPolygon,
  rawPointToDisplay,
  selectionBounds,
} from "../src/services/selectionGeometry.ts";

const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} != ${expected}`);

test("contain coordinates round-trip through letterboxing", () => {
  const geometry = {
    sourceWidth: 1000,
    sourceHeight: 500,
    viewportWidth: 500,
    viewportHeight: 500,
    objectFit: "contain",
    mirrored: false,
  };
  const display = rawPointToDisplay({ x: 0.25, y: 0.8 }, geometry);
  close(display.x, 125);
  close(display.y, 325);
  const raw = displayPointToRaw(display, geometry);
  close(raw.x, 0.25);
  close(raw.y, 0.8);
  assert.equal(displayPointToRaw({ x: 250, y: 40 }, geometry), null);
});

test("cover coordinates compensate crop and camera mirror", () => {
  const geometry = {
    sourceWidth: 400,
    sourceHeight: 800,
    viewportWidth: 400,
    viewportHeight: 400,
    objectFit: "cover",
    mirrored: true,
  };
  const raw = { x: 0.2, y: 0.5 };
  const display = rawPointToDisplay(raw, geometry);
  close(display.x, 320);
  close(display.y, 200);
  const roundTrip = displayPointToRaw(display, geometry);
  close(roundTrip.x, raw.x);
  close(roundTrip.y, raw.y);
});

test("face hull rejects background points and accepts skin-area points", () => {
  const hull = convexHull([
    { x: 0.25, y: 0.2 }, { x: 0.75, y: 0.2 },
    { x: 0.8, y: 0.8 }, { x: 0.2, y: 0.8 },
    { x: 0.5, y: 0.5 },
  ]);
  assert.equal(pointInPolygon({ x: 0.5, y: 0.55 }, hull), true);
  assert.equal(pointInPolygon({ x: 0.05, y: 0.5 }, hull), false);
});

test("polygon validation and bounds preserve authored control points", () => {
  const simple = [
    { x: 0.2, y: 0.2 }, { x: 0.6, y: 0.2 },
    { x: 0.65, y: 0.6 }, { x: 0.25, y: 0.7 },
  ];
  const crossing = [simple[0], simple[2], simple[1], simple[3]];
  assert.equal(isSimplePolygon(simple), true);
  assert.equal(isSimplePolygon(crossing), false);
  assert.deepEqual(selectionBounds(simple).polygon, simple);
});
