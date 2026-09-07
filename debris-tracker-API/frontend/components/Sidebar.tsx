"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  LayoutGrid,
  Globe2,
  Boxes,
  Radar,
  Trash2,
  Waves,
  BellRing,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutGrid },
  { href: "/map", label: "Orbital Map", icon: Globe2 },
  { href: "/objects", label: "Objects", icon: Boxes },
  { href: "/conjunctions", label: "Conjunctions", icon: Radar },
  { href: "/debris", label: "Debris Priority", icon: Trash2 },
  { href: "/cascade", label: "Cascade Simulator", icon: Waves },
  { href: "/alerts", label: "Alerts", icon: BellRing },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-20 flex w-56 flex-col border-r border-border bg-panel">
      <div className="flex h-14 items-center border-b border-border px-5">
        <span className="text-sm font-semibold tracking-tight">
          ORBIT<span className="text-accent">GUARD</span>
        </span>
      </div>
      <nav className="flex-1 overflow-y-auto py-3">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 border-l-2 px-5 py-2.5 text-sm transition-colors",
                active
                  ? "border-accent bg-white/[0.03] text-text"
                  : "border-transparent text-text-muted hover:text-text"
              )}
            >
              <Icon size={16} strokeWidth={1.75} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border px-5 py-3 text-xs text-text-muted">
        Decision-support platform.
        <br />
        Not an operational flight system.
      </div>
    </aside>
  );
}
