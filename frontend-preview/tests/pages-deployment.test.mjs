import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { publicAsset } from "../src/lib/assets.ts";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("public assets resolve safely at the local root", () => {
  assert.equal(publicAsset("/assets/brand/MIRA_logo_primary.svg"), "/assets/brand/MIRA_logo_primary.svg");
  assert.equal(publicAsset("blob:photo"), "blob:photo");
});

test("the application uses hash routing for Pages deep links", async () => {
  const app = await read("src/App.tsx");
  assert.match(app, /HashRouter/);
  assert.doesNotMatch(app, /BrowserRouter/);
});

test("Vite supports the repository subpath and Pages build enables demo mode", async () => {
  const [vite, pkg] = await Promise.all([
    read("vite.config.ts"),
    read("package.json"),
  ]);
  assert.match(vite, /VITE_BASE_PATH/);
  assert.match(pkg, /VITE_BASE_PATH=\/MIRA-\//);
  assert.match(pkg, /VITE_DEMO_MODE=true/);
  assert.match(pkg, /preview:pages/);
});
