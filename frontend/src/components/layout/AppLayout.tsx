import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Users,
  LayoutDashboard,
  Clock,
  ShieldCheck,
  MonitorDot,
  FileText,
  LogOut,
  Menu,
  X,
  ScanFace,
  Moon,
  Sun,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Funcionários", href: "/employees", icon: Users },
  { label: "Presença & Ponto", href: "/attendance", icon: Clock },
  { label: "Terminais", href: "/terminals", icon: MonitorDot },
  { label: "Relatórios", href: "/reports", icon: FileText },
  { label: "Privacidade & LGPD", href: "/privacy", icon: ShieldCheck },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const toggleTheme = () => {
    setDark(!dark);
    document.documentElement.classList.toggle("dark");
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    navigate("/login");
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar (Desktop + Mobile Drawer) */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex flex-col border-r bg-card transition-all duration-300 lg:static",
          mobileOpen ? "translate-x-0 w-72 max-w-[85vw] shadow-2xl" : "-translate-x-full lg:translate-x-0",
          collapsed ? "lg:w-20" : "lg:w-64"
        )}
      >
        <div className="flex h-16 items-center justify-between border-b px-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
              <ScanFace className="h-6 w-6" />
            </div>
            {(!collapsed || mobileOpen) && (
              <span className="font-bold tracking-tight text-lg text-foreground">
                FaceAccess
              </span>
            )}
          </div>

          {/* Desktop Collapse / Mobile Close */}
          <button
            onClick={() => {
              if (window.innerWidth < 1024) {
                setMobileOpen(false);
              } else {
                setCollapsed(!collapsed);
              }
            }}
            className="rounded-lg p-2 text-muted-foreground hover:bg-muted"
            aria-label="Alternar Menu"
          >
            <X className="h-5 w-5 lg:hidden" />
            <span className="hidden lg:inline">
              {collapsed ? <Menu className="h-5 w-5" /> : <X className="h-5 w-5" />}
            </span>
          </button>
        </div>

        <nav className="flex-1 space-y-1 p-3 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = location.pathname === item.href;
            return (
              <Link
                key={item.href}
                to={item.href}
                onClick={() => setMobileOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
                title={collapsed ? item.label : undefined}
              >
                <Icon className="h-5 w-5 shrink-0" />
                {(!collapsed || mobileOpen) && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="border-t p-3 space-y-1">
          <Link
            to="/kiosk"
            onClick={() => setMobileOpen(false)}
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-primary hover:bg-primary/10 transition-colors"
          >
            <ScanFace className="h-5 w-5 shrink-0" />
            {(!collapsed || mobileOpen) && <span>Modo Kiosk (Totem)</span>}
          </Link>
          <button
            onClick={toggleTheme}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors"
          >
            {dark ? <Sun className="h-5 w-5 shrink-0" /> : <Moon className="h-5 w-5 shrink-0" />}
            {(!collapsed || mobileOpen) && <span>{dark ? "Modo Claro" : "Modo Escuro"}</span>}
          </button>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-destructive hover:bg-destructive/10 transition-colors"
          >
            <LogOut className="h-5 w-5 shrink-0" />
            {(!collapsed || mobileOpen) && <span>Sair</span>}
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        <header className="flex h-16 shrink-0 items-center justify-between border-b bg-card px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="rounded-lg p-2 text-muted-foreground hover:bg-muted lg:hidden"
            >
              <Menu className="h-6 w-6" />
            </button>
            <h1 className="text-base sm:text-xl font-semibold tracking-tight truncate">
              Painel Administrativo
            </h1>
          </div>

          <div className="flex items-center gap-2 sm:gap-4">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-[11px] sm:text-xs font-medium text-emerald-600 dark:text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
              <span className="hidden sm:inline">IA Local Ativa (CPU/ONNX)</span>
              <span className="sm:hidden">IA Local</span>
            </span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
