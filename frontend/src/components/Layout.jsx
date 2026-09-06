import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/lib/constants";
import {
  LayoutDashboard, Users2, Workflow, MapPin, AlertTriangle,
  Wallet, UserCog, Timer, LogOut, Sun,
} from "lucide-react";

const NAV = {
  OWNER: [
    ["/", "Dashboard", LayoutDashboard],
    ["/leads", "Leads", Users2],
    ["/ecps", "ECP Projects", Workflow],
    ["/site-visits", "Site Visits", MapPin],
    ["/escalations", "Escalations", AlertTriangle],
    ["/payments", "Payments", Wallet],
    ["/users", "Users", UserCog],
    ["/sla", "SLA Config", Timer],
  ],
  MANAGER: [
    ["/", "Dashboard", LayoutDashboard],
    ["/leads", "Leads", Users2],
    ["/ecps", "ECP Projects", Workflow],
    ["/site-visits", "Site Visits", MapPin],
    ["/payments", "Payments", Wallet],
  ],
  LEAD: [
    ["/", "Dashboard", LayoutDashboard],
    ["/leads", "Leads", Users2],
    ["/ecps", "ECP Projects", Workflow],
  ],
  REGISTRATION: [
    ["/", "Dashboard", LayoutDashboard],
    ["/ecps", "ECP Projects", Workflow],
  ],
  ACCOUNTS: [
    ["/", "Dashboard", LayoutDashboard],
    ["/ecps", "ECP Projects", Workflow],
    ["/payments", "Payments", Wallet],
  ],
  DISPATCH: [
    ["/", "Dashboard", LayoutDashboard],
    ["/ecps", "ECP Projects", Workflow],
  ],
  INSTALLATION: [
    ["/", "Dashboard", LayoutDashboard],
    ["/site-visits", "Site Visits", MapPin],
    ["/ecps", "ECP Projects", Workflow],
  ],
};

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const items = NAV[user?.role] || NAV.OWNER;

  return (
    <div className="min-h-screen flex bg-background">
      <aside className="w-60 shrink-0 command-header text-slate-200 flex flex-col fixed h-screen">
        <div className="px-5 py-5 border-b border-white/10">
          <div className="flex items-center gap-2">
            <Sun className="text-amber-400" size={22} />
            <div>
              <div className="font-head font-extrabold text-white text-lg leading-none">ECP Tracker</div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mt-1">Ops Command</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {items.map(([path, label, Icon]) => {
            const active = loc.pathname === path || (path !== "/" && loc.pathname.startsWith(path));
            return (
              <button
                key={path}
                data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
                onClick={() => nav(path)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  active ? "bg-sky-600 text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"
                }`}
              >
                <Icon size={17} /> {label}
              </button>
            );
          })}
        </nav>
        <div className="p-3 border-t border-white/10">
          <div className="px-2 py-2">
            <div className="text-sm font-semibold text-white truncate">{user?.name}</div>
            <div className="text-[11px] font-mono uppercase tracking-wide text-sky-300">{ROLE_LABELS[user?.role]}</div>
          </div>
          <button
            data-testid="logout-button"
            onClick={() => { logout(); nav("/login"); }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-red-600 hover:text-white transition-colors"
          >
            <LogOut size={16} /> Log out
          </button>
        </div>
      </aside>
      <main className="flex-1 ml-60 min-h-screen">{children}</main>
    </div>
  );
}
