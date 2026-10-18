import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { AddProduct } from "../components/beauty-kit/AddProduct";
import { getBeautyKit, getProductCategories } from "../services/products";
import { useService } from "../hooks/useService";
import { setProductUseMode } from "../services/productMode";
import { mergeUserProducts, productMatchesQuery } from "../services/productLibrary";
import { getTutorial } from "../services/tutorial";
import type { MakeupAction } from "../types/tutorial";
import { publicAsset } from "../lib/assets";

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
  const [, refreshLibrary] = useState(0);
  const { data, error, notice } = useService(getBeautyKit);
  const { data: categories } = useService(getProductCategories);
  const { data: tutorialActions } = useService(getTutorial);
  const shownProducts = mergeUserProducts(data ?? []);
  const search = query.trim().toLocaleLowerCase();
  const filteredProducts = shownProducts.filter((product) => productMatchesQuery(product, search));
  const visibleCategories = categories?.filter((category) =>
    !search || filteredProducts.some((product) => product.category === category),
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
            src={publicAsset("assets/hero/beauty-kit-flatlay.jpg")}
            alt="化妆刷与眼影盘平铺展示"
          />
          <figcaption>妆容灵感图 · 非已录入产品</figcaption>
        </figure>
      </section>
      <div className="action-row kit-toolbar">
        <span>{data ? `我的产品库 ${shownProducts.length} 件` : error ? "暂时无法读取我的产品库" : "正在读取产品…"}</span>
        <AddProduct onProductAdded={() => refreshLibrary((value) => value + 1)} />
      </div>
      {error && <p role="alert">{error} 请刷新后重试。</p>}
      {notice && <p role="status">{notice}</p>}
      <p className="demo-footnote">“搜索我的产品库”只查找你已加入的产品；“搜索产品库”浏览项目当前内置目录。当前目录未连接欧莱雅官方产品数据库。</p>
      <div className="kit-case-link">
        <div><span className="eyebrow">FIVE ACTIONS / PRODUCT MATCHING</span><h2>从教程需求，看已有产品能否替代</h2><p>A01–A05 五步参考：查看近似产品、替代条件、差异与效果影响。</p></div>
        <Button asChild variant="outline"><Link to="/product-alternatives" state={{ returnTo: "/beauty-kit" }}>查看产品替代方案 →</Link></Button>
      </div>
      <div className="kit-search">
        <label htmlFor="kit-search">搜索我的产品库</label>
        <input id="kit-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="产品名称、品牌、类型或色号" />
        <p role="status">在我的产品库中找到 {filteredProducts.length} 件；这些产品会随当前 Kit 进入产品匹配。</p>
        {query && <Button variant="tertiary" onClick={() => setQuery("")}>清除搜索</Button>}
      </div>
      {search && !filteredProducts.length && <div className="kit-empty"><strong>我的产品库中没有匹配项</strong><p>换一个名称、品牌或色号，或使用“搜索产品库”添加产品。</p></div>}
      {visibleCategories?.map((c) => (
        <details className="category" key={`${c}-${Boolean(search)}`} open={!!search || c === "眼部" || c === "面部"}>
          <summary>
            <h2>{c}</h2>
            <span>
              {filteredProducts.filter((product) => product.category === c).length} 件
            </span>
            <ChevronDown size={16} />
          </summary>
          {filteredProducts
            .filter((product) => product.category === c)
            .map((p) => (
              <div className="product" key={p.id}>
                {p.productImage ? (
                  <img
                    className="product-image"
                    src={p.productImage}
                    alt={`${p.productName}产品陈列示意图`}
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
                    <span className="kit-example-badge">我的产品库</span>
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
          {!shownProducts.some((product) => product.category === c) && (
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
