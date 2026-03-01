import { NavLink } from "react-router-dom";
import {
  MessageSquare,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { icon: MessageSquare, label: "Сообщения", to: "/" },
  { icon: BarChart3, label: "Аналитика", to: "/dashboard" },
];

export default function Sidebar() {
  return (
    <aside className="w-[220px] min-h-screen bg-sidebar border-r border-sidebar-border flex flex-col py-6 px-3">
      <div className="px-4 mb-6">
        <h2 className="text-base font-bold text-foreground tracking-tight">
          Ticket Tamer
        </h2>
        <p className="text-xs text-muted-foreground">ЭРИС</p>
      </div>
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-4 h-10 rounded-lg text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-muted hover:bg-accent/50",
              )
            }
          >
            <item.icon className="w-5 h-5" strokeWidth={1.5} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
