import { coachResponses, coachIntents } from "../mocks/coach";
import { demo } from "./base";
import type { CoachIntent } from "../types/guidance";
export const getCoachResponse = (intent: CoachIntent) =>
  demo(coachResponses[intent]);
export const getCoachIntents = () => demo(coachIntents);
export const recordCompletedStep = (id: string) => {
  const ids = getCompletedSteps();
  if (!ids.includes(id))
    sessionStorage.setItem("mira-completed", JSON.stringify([...ids, id]));
};
export const getCompletedSteps = (): string[] => {
  try {
    return JSON.parse(sessionStorage.getItem("mira-completed") || "[]");
  } catch {
    return [];
  }
};
export const resetCoach = () => sessionStorage.removeItem("mira-completed");
