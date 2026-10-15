import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { AddProduct } from "../components/beauty-kit/AddProduct";
import { getBeautyKit, getProductCategories } from "../services/products";
import { useService } from "../hooks/useService";
import { setProductUseMode } from "../services/productMode";
import { sampleProducts } from "../mocks/products";
import { getTutorial } from "../services/tutorial";
import type { MakeupAction } from "../types/tutorial";

const stepNeedles: Record<string, string[]> = {
  "palette-a": ["眼影", "shadow"],
  "product-neutral-palette": ["眼影", "shadow"],
  "display-eye-primer": ["眼部打底", "眼皮打底", "eye primer"],
  "display-eye-liner": ["眼线", "eyeliner"],
  "display-shadow-matte": ["哑光过渡色眼影", "哑光深色眼影", "matte transition shadow", "matte deep shadow"],
  "display-shadow-shimmer": ["珠光眼影", "shimmer shadow"],
  "display-week2-concept-palette": ["眼影", "浅米色", "深棕色", "香槟色"],
  "display-panorama-mascara": ["睫毛", "mascara"],
};
function stepReference(productId: string, actions?: MakeupAction[]) {
  const terms = stepNeedles[productId];
  if (!terms || !actions) return [];
  return actions
    .filter((action) => terms.some((term) => action.productRequirement.toLowerCase().includes(term)))
    .map((action) => action.name);
}
export default function BeautyKit() {
  const [query, setQuery] = useState("");
  const { data, error, notice } = useService(getBeautyKit);
  const { data: categories } = useService(getProductCategories);
  const { data: tutorialActions } = useService(getTutorial);
  const shownProducts = [
    ...(data ?? []).map((product) => ({ product, isExample: false })),
    ...sampleProducts.map((product) => ({ product, isExample: true })),
  ];
  const search = query.trim().toLocaleLowerCase();
  const filteredProducts = shownProducts.filter(({ product }) =>
    [product.productName, product.brand, product.category, ...product.shades.map((shade) => shade.shadeName)]
      .some((value) => value.toLocaleLowerCase().includes(search)),
  );
  const visibleCategories = categories?.filter((category) =>
    !search || filteredProducts.some(({ product }) => product.category === category),
  );
  return (
    <Page
      eyebrow="02 / 产品匹配"
      title="我的美妆工具库"
      backTo="/tutorial/recipe"
      progress={25}
    >
      <section className="kit-intro" aria-label="工具库概览">
        <div className="kit-intro-copy">
          <span className="eyebrow">MY BEAUTY KIT</span>
          <h2>把常用的颜色与工具，放在同一处。</h2>
          <p>欧莱雅黑客松概念陈列：从产品类别出发，查看它们与当前教程步骤的关系。</p>
        </div>
        <figure className="kit-intro-image">
          <img
            src="/assets/hero/beauty-kit-flatlay.jpg"
            alt="化妆刷与眼影盘平铺展示"
          />
          <figcaption>妆容灵感图 · 非已录入产品</figcaption>
        </figure>
      </section>
      <div className="action-row kit-toolbar">
        <span>{data ? `产品资料 ${data.length} 件 · 陈列示例 ${sampleProducts.length} 件` : error ? "产品资料未加载 · 仍可浏览陈列示例" : "正在读取产品…"}</span>
        <AddProduct />
      </div>
      {error && <p role="alert">{error} 请刷新重试；下方陈列示例不代表已加载的产品。</p>}
      {notice && <p role="status">{notice}</p>}
      <p className="demo-footnote">当前资料来自演示数据。品牌系列名称参考欧莱雅巴黎官网；陈列示例的色块并非官方色样，也不代表中国市场在售或官方合作。示例不参与匹配，步骤提示只按产品类别对应。</p>
      <div className="kit-case-link">
        <div><span className="eyebrow">FIVE ACTIONS / PRODUCT MATCHING</span><h2>从教程需求，看已有产品能否替代</h2><p>A01–A05 固定案例：查看近似产品、替代条件、差异与 Impact。</p></div>
        <Button asChild variant="outline"><Link to="/product-alternatives" state={{ returnTo: "/beauty-kit" }}>查看产品替代方案 →</Link></Button>
      </div>
      <div className="kit-search">
        <label htmlFor="kit-search">查找产品或色号</label>
        <input id="kit-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入产品、品牌、类别或色号" />
        <p role="status">显示 {filteredProducts.length} 件资料与陈列示例；搜索不会改变匹配范围。</p>
        {query && <Button variant="tertiary" onClick={() => setQuery("")}>清除搜索</Button>}
      </div>
      {search && !filteredProducts.length && <p>没有找到相关产品，试试其他名称或色号。</p>}
      {visibleCategories?.map((c) => (
        <details className="category" key={`${c}-${Boolean(search)}`} open={!!search || c === "眼部" || c === "面部"}>
          <summary>
            <h2>{c}</h2>
            <span>
              {filteredProducts.filter(({ product }) => product.category === c).length} 件展示
            </span>
            <ChevronDown size={16} />
          </summary>
          {filteredProducts
            .filter(({ product }) => product.category === c)
            .map(({ product: p, isExample }) => (
              <div className="product" key={p.id}>
                {p.productImage ? (
                  <img
                    className="product-image"
                    src={p.productImage}
                    alt={p.productName}
                  />
                ) : (
                  <div className="product-shade-preview" role="img" aria-label={`${p.productName}的色号示意`}>
                    {p.shades.length ? p.shades.slice(0, 4).map((shade) => (
                      <span key={shade.shadeName} style={{ backgroundColor: shade.hex }} />
                    )) : <span className="product-shade-empty">暂无产品图片</span>}
                  </div>
                )}
                <div>
                  <div className="kit-product-meta">
                    <span className="eyebrow">{p.brand}</span>
                    {isExample && <span className="kit-example-badge">陈列示例 · 不参与匹配</span>}
                  </div>
                  <h2>{p.productName}</h2>
                  {stepReference(p.id, tutorialActions).length > 0 && (
                    <p className="kit-step-reference">
                      教程步骤参考：{stepReference(p.id, tutorialActions).join("、")}
                    </p>
                  )}
                  <div className="swatches">
                    {p.shades.map((s) => (
                      <div key={s.shadeName}>
                        <span style={{ background: s.hex }} />
                        <small>{s.shadeName}</small>
                        <small>{s.finish}</small>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          {!shownProducts.some(({ product }) => product.category === c) && (
            <p className="empty">这一类别还没有产品。</p>
          )}
        </details>
      ))}
      <div className="action-row">
        <Button asChild>
          <Link to="/matching" onClick={() => setProductUseMode("beauty-kit")}>
            匹配当前教程 →
          </Link>
        </Button>
      </div>
    </Page>
  );
}
