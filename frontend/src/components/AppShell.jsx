import { NavLink, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import {
  LayoutDashboard,
  MessageCircle,
  Link2,
  LogOut,
  Menu,
  X,
  Sparkles,
  Moon,
  Sun,
  Newspaper,
  LayoutGrid,
  Bell,
  Check,
  RotateCcw,
  Scale,
} from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import FoleoLogo from "./FoleoLogo";
import { alerts } from "../services/api";

const NAV_ITEMS = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Portfolio" },
  { to: "/optimize", icon: Scale, label: "Optimize" },
  { to: "/chat", icon: MessageCircle, label: "Assistant" },
  { to: "/news", icon: Newspaper, label: "News" },
  { to: "/baskets", icon: LayoutGrid, label: "Baskets" },
  { to: "/alerts", icon: Bell, label: "Alerts" },
  { to: "/broker", icon: Link2, label: "Broker" },
];

function SidebarLink({ to, icon: Icon, label, onClick }) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive }) =>
        `group flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-medium transition-all duration-300 ${isActive
          ? "bg-[var(--color-surface-overlay)] text-[var(--color-text-primary)] shadow-sm"
          : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-raised)]"
        }`
      }
    >
      <Icon size={17} strokeWidth={1.8} />
      <span>{label}</span>
    </NavLink>
  );
}

function AlertBell() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const fetchAlerts = async () => {
    try {
      const res = await alerts.list();
      setItems(res || []);
    } catch {
      // silently ignore — notification bell should never break the app shell
    }
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const unread = items.filter((a) => a.is_triggered && !a.is_read);

  const handleDismiss = async (id) => {
    try {
      await alerts.dismiss(id);
      fetchAlerts();
    } catch {
      // ignore
    }
  };

  const handleReset = async (id) => {
    try {
      await alerts.reset(id);
      fetchAlerts();
    } catch {
      // ignore
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative p-2 rounded-xl bg-[var(--color-surface-overlay)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-border)] transition-all duration-300 shadow-sm border border-[var(--color-border)]"
        title="Alerts"
      >
        <Bell size={14} />
        {unread.length > 0 && (
          <span className="absolute -top-1.5 -right-1.5 min-w-[16px] h-[16px] px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center">
            {unread.length > 9 ? "9+" : unread.length}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.2 }}
            className="absolute bottom-full mb-2 left-0 w-80 max-h-96 overflow-y-auto glass-card p-3 shadow-2xl z-50"
          >
            <p className="text-[11px] font-bold uppercase tracking-[2px] text-[var(--color-text-muted)] px-2 py-1">
              Triggered Alerts
            </p>
            {unread.length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)] px-2 py-4 text-center">No new alerts.</p>
            ) : (
              <div className="space-y-1.5 mt-1">
                {unread.map((a) => (
                  <div key={a.id} className="p-3 rounded-xl bg-[var(--color-surface-overlay)] border border-[var(--color-border-subtle)]">
                    <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                      {a.symbol} crossed {a.direction} ₹{a.target_price}
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <button
                        onClick={() => handleDismiss(a.id)}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-raised)] transition-colors"
                      >
                        <Check size={12} /> Dismiss
                      </button>
                      <button
                        onClick={() => handleReset(a.id)}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold text-[var(--color-text-secondary)] hover:text-amber-500 hover:bg-amber-500/10 transition-colors"
                      >
                        <RotateCcw size={12} /> Reset
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const isDark = theme === "dark";

  const sidebar = (
    <div className="flex flex-col h-full bg-[var(--color-surface)]">
      {/* Logo */}
      <div className="px-6 py-8 flex items-center">
        <FoleoLogo size="lg" className="drop-shadow-sm" />
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-4 space-y-1 mt-4">
        <p className="px-4 mb-4 text-[10px] font-bold uppercase tracking-[2px] text-[var(--color-text-muted)]">Menu</p>
        {NAV_ITEMS.map((item) => (
          <SidebarLink
            key={item.to}
            {...item}
            onClick={() => setMobileOpen(false)}
          />
        ))}
      </nav>

      {/* User section */}
      <div className="px-5 py-5 border-t border-[var(--color-border)]">
        <div className="flex items-center justify-between mb-4">
          <span className="text-[11px] font-bold uppercase tracking-[2px] text-[var(--color-text-muted)] ml-2">Theme</span>
          <div className="flex items-center gap-2">
            <AlertBell />
            <button
              onClick={toggleTheme}
              className="p-2 rounded-xl bg-[var(--color-surface-overlay)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-border)] transition-all duration-300 shadow-sm border border-[var(--color-border)] flex items-center gap-2"
              title="Toggle Theme"
            >
              {isDark ? <Sun size={14} /> : <Moon size={14} />}
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between bg-[var(--color-surface-card)] rounded-2xl p-3 border border-[var(--color-border-subtle)]">
          <div className="min-w-0 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[var(--color-surface-overlay)] flex items-center justify-center text-sm font-semibold text-[var(--color-text-primary)] uppercase shrink-0">
              {(user?.email || "U").charAt(0)}
            </div>
            <p className="text-sm font-medium text-[var(--color-text-secondary)] truncate max-w-[100px]">
              {user?.email || user?.userId || "User"}
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="p-2.5 text-[var(--color-text-muted)] hover:text-red-500 transition-colors duration-300 rounded-xl hover:bg-red-500/10"
            title="Logout"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-[var(--color-surface)] text-[var(--color-text-primary)]">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-72 flex-col border-r border-[var(--color-border)] shadow-[var(--color-border)_1px_0_0_0]">
        {sidebar}
      </aside>

      {/* Mobile overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/40 backdrop-blur-md z-40 lg:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 320 }}
              className="fixed left-0 top-0 bottom-0 w-72 z-50 bg-[var(--color-surface)] border-r border-[var(--color-border)] lg:hidden shadow-2xl"
            >
              {sidebar}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 bg-[var(--color-surface)]">
        {/* Top bar (mobile) */}
        <header className="lg:hidden flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]/80 backdrop-blur-xl sticky top-0 z-30">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2.5 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors rounded-xl bg-[var(--color-surface-overlay)]"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center mt-1">
            <FoleoLogo size="sm" className="drop-shadow-sm" />
          </div>
          <button
            onClick={toggleTheme}
            className="p-2.5 text-[var(--color-text-secondary)] transition-colors rounded-xl bg-[var(--color-surface-overlay)]"
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto relative z-10">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
              className="min-h-full"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
