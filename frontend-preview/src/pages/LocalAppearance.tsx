import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { LocalAppearanceCard } from "../components/preferences/LocalAppearanceCard";
import { hasFaceProfile } from "../services/face";
import {
  getPreferencePreview,
  clearPreferencePreview,
} from "../services/preferencePreview";
export default function LocalAppearance() {
  const [image] = useState(getPreferencePreview);
  useEffect(() => () => clearPreferencePreview(), []);
  const scanned = hasFaceProfile();
  return (
    <Page
      eyebrow="03 / 适配面部"
      title="局部呈现偏好"
      backTo="/beauty-profile"
      progress={75}
    >
      {scanned ? (
        <>
          <LocalAppearanceCard editor image={image} />
          <div className="action-row">
            <Button asChild variant="outline">
              <Link to="/beauty-profile">返回面部档案</Link>
            </Button>
            <Button asChild>
              <Link to="/my-tutorial">继续生成我的教程 →</Link>
            </Button>
          </div>
        </>
      ) : (
        <>
          <p>完成面部扫描后，可选择需要单独设置的区域。</p>
          <Button asChild>
            <Link to="/face-scan">前往面部扫描 →</Link>
          </Button>
        </>
      )}
    </Page>
  );
}
