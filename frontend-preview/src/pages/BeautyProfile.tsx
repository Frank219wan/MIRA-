import { Link } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Card, Tag } from "../components/ui/primitives";
import { Button } from "../components/ui/button";
import { getFaceProfile, hasFaceProfile } from "../services/face";
import { useService } from "../hooks/useService";
export default function BeautyProfile() {
  const { data, error } = useService(getFaceProfile);
  if (!hasFaceProfile())
    return (
      <Page eyebrow="03 / ADAPT" title="我的美妆面部档案">
        <p>你尚未启用面部档案，可以先了解扫描说明，或继续当前教程。</p>
        <div className="equal-actions">
          <Button asChild variant="outline">
            <Link to="/face-scan">了解面部扫描</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/my-tutorial">继续生成教程</Link>
          </Button>
        </div>
      </Page>
    );
  return (
    <Page
      eyebrow="03 / ADAPT"
      title="我的美妆面部档案"
      description="记录特征，只为让操作建议更贴合你。以下为示例档案。"
    >
      {error && <p>{error}</p>}
      {data && (
        <>
          <div className="profile-grid">
            <Card>
              <span className="eyebrow">A / PROPORTIONS</span>
              <h2>面部比例</h2>
              <dl>
                {data.proportions.map((x) => (
                  <div key={x.label}>
                    <dt>{x.label}</dt>
                    <dd>{x.value}</dd>
                  </div>
                ))}
              </dl>
              <p>比例用于定位，不代表美的标准。</p>
            </Card>
            <Card>
              <span className="eyebrow">B / STRUCTURE</span>
              <h2>局部结构</h2>
              <dl>
                {data.structure.map((x) => (
                  <div key={x.label}>
                    <dt>{x.label}</dt>
                    <dd>{x.value}</dd>
                  </div>
                ))}
              </dl>
            </Card>
            <Card>
              <span className="eyebrow">C / COLOR</span>
              <h2>色彩倾向</h2>
              <dl>
                {[
                  ["底色倾向", data.undertone],
                  ["明度", data.value],
                  ["彩度", data.chroma],
                  ["对比度", data.contrast],
                  ["四季型参考", data.season],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          </div>
          <div className="notice">
            <Tag>本次教程可能调整</Tag>
            <p>外眼角范围 / 晕染方向 / 中央提亮位置</p>
            <small>色彩类型仅作为产品和配色建议的辅助参考。</small>
          </div>
        </>
      )}
      <div className="action-row">
        <Button asChild variant="outline">
          <Link to="/face-scan">返回扫描说明</Link>
        </Button>
        <Button asChild>
          <Link to="/my-tutorial">查看我的专属教程 →</Link>
        </Button>
      </div>
    </Page>
  );
}
