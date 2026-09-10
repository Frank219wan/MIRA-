import { personalizedTutorial } from "../mocks/personalizedTutorial";
import { demo } from "./base";
import { hasFaceProfile } from "./face";
export const getPersonalizedTutorial = () =>
  demo(personalizedTutorial(hasFaceProfile()));
export const savePersonalizedTutorial = async () => {
  const actions = await getPersonalizedTutorial();
  localStorage.setItem(
    "mira-saved-tutorial",
    JSON.stringify({
      savedAt: new Date().toISOString(),
      faceAdapted: hasFaceProfile(),
      actions,
    }),
  );
  return true;
};
