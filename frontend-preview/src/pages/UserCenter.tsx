import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import {
  getDemoUser,
  demoLogin,
  demoLogout,
  getSavedTutorials,
  removeTutorial,
} from "../services/userCenter";
import { getFaceProfileDTO, setFaceConsent } from "../services/face";
export default function UserCenter() {
  const nav = useNavigate();
  const [user, setUser] = useState(getDemoUser);
  const [name, setName] = useState("");
  const [tutorials, setTutorials] = useState(getSavedTutorials);
  const [profile, setProfile] = useState(getFaceProfileDTO);
  const [error, setError] = useState("");
  if (!user)
    return (
      <Page title="欢迎来到 MIRA 映己" eyebrow="个人空间" backTo="/">
        <form
          className="demo-login"
          onSubmit={(e) => {
            e.preventDefault();
            try {
              demoLogin(name);
              setUser(getDemoUser());
            } catch {
              setError("浏览器无法保存登录状态，请检查存储设置。");
            }
          }}
        >
          <h2>本机个人空间</h2>
          <p>无需密码，不创建真实账号。</p>
          <label htmlFor="demo-name">昵称</label>
          <input
            id="demo-name"
            value={name}
            maxLength={30}
            placeholder="MIRA 体验者"
            onChange={(e) => setName(e.target.value)}
          />
          <Button type="submit">进入我的空间</Button>
          <p className="face-scan-note">
            教程仅保存在当前浏览器，不上传账号云端。
          </p>
          {error && <p role="alert">{error}</p>}
        </form>
      </Page>
    );
  return (
    <Page title={`${user}的个人空间`} eyebrow="个人中心" backTo="/">
      <div className="section-topline">
        <span>本机个人空间 · 退出不会删除收藏</span>
        <Button
          variant="tertiary"
          onClick={() => {
            demoLogout();
            setUser(null);
          }}
        >
          退出本机个人空间
        </Button>
      </div>
      <section className="account-section">
        <h2>个人档案</h2>
        <p>
          {profile
            ? "已有本次面部档案，可用于调整教程。"
            : "尚无可用面部档案。扫描后可选择在当前会话保留数值。"}
        </p>
        <div className="action-row">
          <Button
            variant="outline"
            onClick={() => nav(profile ? "/beauty-profile" : "/face-scan")}
          >
            {profile ? "查看面部档案" : "建立面部档案"}
          </Button>
          {profile && (
            <Button
              variant="tertiary"
              onClick={() => {
                setFaceConsent(false);
                setProfile(undefined);
              }}
            >
              清除面部档案
            </Button>
          )}
        </div>
      </section>
      <section className="account-section">
        <h2>
          我的教程 <span className="account-count">{tutorials.length}</span>
        </h2>
        <p className="face-scan-note">
          保存在当前浏览器；清除网站数据会删除收藏，不同昵称共用本机收藏。
        </p>
        {!tutorials.length ? (
          <p>还没有保存教程。完成跟做后，可点击“保存这次教程”。</p>
        ) : (
          tutorials.map((t) => (
            <article className="account-tutorial" key={t.id}>
              <div>
                <Link
                  className="text-link"
                  to={`/account/tutorial/${encodeURIComponent(t.id)}`}
                >
                  {t.title} ↗
                </Link>
                <p>
                  {t.actions.length} 个步骤 ·{" "}
                  {t.faceAdapted ? "已使用扫描档案" : "基础或参考面部方案"} ·{" "}
                  {new Date(t.savedAt).toLocaleDateString("zh-CN")}
                </p>
              </div>
              <Button
                variant="tertiary"
                onClick={() => {
                  try {
                    removeTutorial(t.id);
                    setTutorials(getSavedTutorials());
                  } catch {
                    setError("删除失败，请检查浏览器存储。");
                  }
                }}
              >
                移除收藏
              </Button>
            </article>
          ))
        )}
        <div className="action-row">
          <Button asChild variant="outline">
            <Link to="/tutorial">从教程开始</Link>
          </Button>
        </div>
      </section>
      {error && <p role="alert">{error}</p>}
    </Page>
  );
}
