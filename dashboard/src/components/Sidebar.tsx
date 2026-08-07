"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  {
    section: "Queries",
    items: [
      { href: "/", label: "Query Console", icon: "⌕" },
    ],
  },
  {
    section: "System",
    items: [
      { href: "/tenants", label: "Tenant Overview", icon: "⬡" },
      { href: "/review", label: "Needs-Review Queue", icon: "⚑" },
      { href: "/health", label: "System Health", icon: "◈" },
      { href: "/documents", label: "Document Library", icon: "⊞" },
    ],
  },
  {
    section: "Audit",
    items: [
      { href: "/audit", label: "Enterprise Audit Suite", icon: "✓" },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div>
          <div className="sidebar-logo">Company Brain</div>
          <div className="sidebar-logo-sub">admin console v0.1</div>
        </div>
      </div>

      {NAV.map(group => (
        <div key={group.section} className="nav-section">
          <div className="nav-label">{group.section}</div>
          {group.items.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${pathname === item.href ? "active" : ""}`}
            >
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "13px", width: 16, textAlign: "center" }}>
                {item.icon}
              </span>
              {item.label}
            </Link>
          ))}
        </div>
      ))}
    </aside>
  );
}
