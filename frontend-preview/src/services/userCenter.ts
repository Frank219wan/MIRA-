import type { PersonalizedAction } from "../types/guidance";
export interface SavedTutorial {
  id: string;
  title: string;
  savedAt: string;
  actions: PersonalizedAction[];
  stepNames?: string[];
  faceAdapted?: boolean;
  productMode?: string;
}
const KEY = "mira-tutorials";
function valid(value: unknown): value is SavedTutorial {
  const v = value as SavedTutorial;
  return (
    !!v &&
    typeof v.id === "string" &&
    typeof v.title === "string" &&
    typeof v.savedAt === "string" &&
    Array.isArray(v.actions) &&
    v.actions.every(
      (a) =>
        a &&
        typeof a.actionId === "string" &&
        typeof a.instructions === "string",
    )
  );
}
export function getSavedTutorials(): SavedTutorial[] {
  try {
    const existing = localStorage.getItem(KEY);
    if (existing !== null) {
      const data = JSON.parse(existing);
      return Array.isArray(data) ? data.filter(valid) : [];
    }
    const old = JSON.parse(
      localStorage.getItem("mira-saved-tutorial") || "null",
    );
    if (!old) return [];
    const migrated = { ...old, id: "legacy-saved", title: "此前保存的教程" };
    if (!valid(migrated)) return [];
    localStorage.setItem(KEY, JSON.stringify([migrated]));
    localStorage.removeItem("mira-saved-tutorial");
    return [migrated];
  } catch {
    return [];
  }
}
export function storeTutorial(tutorial: SavedTutorial) {
  if (!valid(tutorial)) throw new Error("教程内容不完整，暂时无法保存。");
  localStorage.setItem(
    KEY,
    JSON.stringify([
      tutorial,
      ...getSavedTutorials().filter((t) => t.id !== tutorial.id),
    ]),
  );
}
export function removeTutorial(id: string) {
  localStorage.setItem(
    KEY,
    JSON.stringify(getSavedTutorials().filter((t) => t.id !== id)),
  );
}
export function getDemoUser(): string | null {
  try {
    return sessionStorage.getItem("mira-demo-user");
  } catch {
    return null;
  }
}
export function demoLogin(name: string) {
  sessionStorage.setItem(
    "mira-demo-user",
    name.trim().slice(0, 30) || "MIRA 体验者",
  );
}
export function demoLogout() {
  sessionStorage.removeItem("mira-demo-user");
}
