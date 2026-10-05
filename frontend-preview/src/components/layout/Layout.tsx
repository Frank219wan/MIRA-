import { useEffect } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { ArrowUpRight, House, ShoppingBag, UserRound } from "lucide-react";
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
        <nav className="header-actions" aria-label="页面导航">
          {pathname !== "/" && (
            <Link className="home-link" to="/">
              <House size={16} />
              返回首页
            </Link>
          )}
          <Link className="kit-link" to="/beauty-kit">
            <ShoppingBag size={16} />
            我的美妆工具库
            <ArrowUpRight size={15} />
          </Link>
          <Link className="account-avatar" to="/account" aria-label="个人中心">
            <UserRound size={20} />
          </Link>
        </nav>
      </header>
      <main key={pathname}>
        <Outlet />
      </main>
      <footer>
        <span>MIRA 映己</span>
        <span>部分结果为演示数据</span>
      </footer>
    </>
  );
}
