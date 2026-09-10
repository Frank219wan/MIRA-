import { actions, stages } from "../mocks/tutorial";
import { demo } from "./base";
import type { TutorialInput } from "../types/tutorial";
export const getTutorial = () => demo(actions);
export const getParsingStages = () => demo(stages);
export const saveTutorialInput = (input: TutorialInput) => {
  sessionStorage.removeItem("mira-completed");
  sessionStorage.setItem("mira-input", JSON.stringify(input));
  return demo(input);
};
