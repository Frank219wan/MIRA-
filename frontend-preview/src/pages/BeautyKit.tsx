import { Link } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { Placeholder } from "../components/ui/primitives";
import { AddProduct } from "../components/beauty-kit/AddProduct";
import { getBeautyKit, getProductCategories } from "../services/products";
import { useService } from "../hooks/useService";
export default function BeautyKit() {
  const { data, error } = useService(getBeautyKit);
  const { data: categories } = useService(getProductCategories);
  return (
    <Page
      eyebrow="02 / MATCH"
      title="我的美妆工具库"
      description="从你已经拥有的开始，发现每一种产品的更多可能。"
    >
      <div className="action-row">
        <span>示例工具库 / 按产品类别整理</span>
        <AddProduct />
      </div>
      {error && <p>{error}</p>}
      {categories?.map((c) => (
        <details className="category" key={c} open={c === "眼部"}>
          <summary>
            <h2>{c}</h2>
            <span>
              {data?.filter((p) => p.category === c).length || 0} 件产品
            </span>
            <ChevronDown size={16} />
          </summary>
          {data
            ?.filter((p) => p.category === c)
            .map((p) => (
              <div className="product" key={p.id}>
                {p.productImage ? (
                  <img
                    className="product-image"
                    src={p.productImage}
                    alt={p.productName}
                  />
                ) : (
                  <Placeholder label="产品图片" />
                )}
                <div>
                  <span className="eyebrow">{p.brand}</span>
                  <h2>{p.productName}</h2>
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
          {!data?.some((p) => p.category === c) && (
            <p className="empty">这一类别还没有产品。</p>
          )}
        </details>
      ))}
      <div className="action-row">
        <span>先用现有产品，完成喜欢的妆容。</span>
        <Button asChild>
          <Link to="/matching">匹配当前教程 →</Link>
        </Button>
      </div>
    </Page>
  );
}
