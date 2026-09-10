import { useEffect } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { ArrowUpRight, ShoppingBag } from "lucide-react";
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
            src="/assets/brand/MIRA_logo_primary.svg"
            alt="MIRA 映己"
          />
        </Link>
        <span className="header-note">你的美，自有章法。</span>
        <Link className="kit-link" to="/beauty-kit">
          <ShoppingBag size={16} />
          我的美妆工具库
          <ArrowUpRight size={15} />
        </Link>
      </header>
      <main key={pathname}>
        <Outlet />
      </main>
      <footer>
        <span>MIRA 映己</span>
        <span>理解妆容，更理解你。</span>
        <span>交互演示版 · 结果为示例</span>
      </footer>
    </>
  );
}
