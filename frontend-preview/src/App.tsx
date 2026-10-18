import LocalAppearance from "./pages/LocalAppearance";
import UserCenter from "./pages/UserCenter";
import SavedTutorial from "./pages/SavedTutorial";
import { HashRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import Home from "./pages/Home";
import TutorialInput from "./pages/TutorialInput";
import Parsing from "./pages/Parsing";
import Recipe from "./pages/Recipe";
import BeautyKit from "./pages/BeautyKit";
import Matching from "./pages/Matching";
import FaceScan from "./pages/FaceScan";
import BeautyProfile from "./pages/BeautyProfile";
import MyTutorial from "./pages/MyTutorial";
import LiveCoach from "./pages/LiveCoach";
import Finish from "./pages/Finish";
import NotFound from "./pages/NotFound";
import ProductAlternatives from "./pages/ProductAlternatives";
export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/account" element={<UserCenter />} />
          <Route path="/account/tutorial/:id" element={<SavedTutorial />} />
          <Route path="/tutorial" element={<TutorialInput />} />
          <Route path="/tutorial/parsing" element={<Parsing />} />
          <Route path="/tutorial/recipe" element={<Recipe />} />
          <Route path="/beauty-kit" element={<BeautyKit />} />
          <Route path="/matching" element={<Matching />} />
          <Route path="/product-alternatives" element={<ProductAlternatives />} />
          <Route path="/face-preferences" element={<LocalAppearance />} />
          <Route path="/face-scan" element={<FaceScan />} />
          <Route path="/beauty-profile" element={<BeautyProfile />} />
          <Route path="/my-tutorial" element={<MyTutorial />} />
          <Route path="/live-coach" element={<LiveCoach />} />
          <Route path="/finish" element={<Finish />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
