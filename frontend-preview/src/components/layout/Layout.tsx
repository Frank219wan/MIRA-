import { useEffect } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { ArrowUpRight, House, ShoppingBag, UserRound } from "lucide-react";
import { apiConfig } from "../../lib/config";
import { publicAsset } from "../../lib/assets";
export function Layout() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return (
    <>
      <header>
        <Link to="/" aria-label="MIRA 映己首页">
          <img
            className="logo"
            src={publicAsset("assets/brand/MIRA_logo_primary.svg")}
            alt="MIRA 映己"
          />
        </Link>
        <nav className="header-actions" aria-label="页面导航">
          {pathname !== "/" && (
            <Link className="home-link" to="/" aria-label="返回首页">
              <House size={16} />
              <span>返回首页</span>
            </Link>
          )}
          <Link className="kit-link" to="/beauty-kit" aria-label="我的美妆工具库">
            <ShoppingBag size={16} />
            <span>我的美妆工具库</span>
            <ArrowUpRight size={15} />
          </Link>
          <Link className="account-avatar" to="/account" aria-label="个人中心">
            <UserRound size={20} />
          </Link>
        </nav>
      </header>
      {apiConfig.demoMode && (
        <div className="deployment-demo-banner" role="status">
          GitHub Pages 演示模式 · 示例教程与明确标记的 Demo 数据在浏览器中运行；面部档案生成与自定义教程解析需要本地服务。
        </div>
      )}
      <main key={pathname}>
        <Outlet />
      </main>
      <footer>
        <span>MIRA 映己</span>
      </footer>
    </>
  );
}
