export type Role = "analyst" | "manager" | "stakeholder" | "compliance" | "admin";

export const ROLE_LABELS: Record<Role, string> = {
  analyst: "Collections Analyst",
  manager: "Portfolio Manager",
  stakeholder: "Senior Stakeholder",
  compliance: "Compliance Reviewer",
  admin: "Admin",
};

export const ROLE_PERMISSIONS: Record<Role, Set<string>> = {
  analyst: new Set(["chat", "borrower", "strategy_read", "workflows", "documents_read"]),
  manager: new Set([
    "chat",
    "borrower",
    "portfolio_read",
    "strategy_run",
    "workflows",
    "audit_read",
    "documents_read",
  ]),
  stakeholder: new Set(["chat", "borrower", "strategy_read", "audit_read", "documents_read", "portfolio_read"]),
  compliance: new Set([
    "chat",
    "borrower",
    "strategy_read",
    "audit_read",
    "audit_export",
    "workflows",
    "documents_read",
  ]),
  admin: new Set([
    "chat",
    "borrower",
    "portfolio_read",
    "strategy_run",
    "workflows",
    "audit_read",
    "audit_export",
    "settings_read",
    "settings_write",
    "documents_read",
  ]),
};

export function normalizeRole(role: string): Role {
  if (role === "executive") return "stakeholder";
  if (role in ROLE_LABELS) return role as Role;
  return "analyst";
}

export function canAccess(role: Role, permission: string): boolean {
  return ROLE_PERMISSIONS[role]?.has(permission) ?? false;
}

export function canSeeNav(role: Role, navKey: string): boolean {
  const map: Record<string, string> = {
    chat: "chat",
    portfolio: "portfolio_read",
    borrower: "borrower",
    strategy: "strategy_read",
    workflows: "workflows",
    documents: "documents_read",
    monitoring: "portfolio_read",
    audit: "audit_read",
    settings: "settings_read",
  };
  // Analysts can open monitoring via strategy_read as a lighter gate
  if (navKey === "monitoring" && canAccess(role, "strategy_read")) return true;
  return canAccess(role, map[navKey] || navKey);
}

export function homePathForRole(role: Role): string {
  switch (role) {
    case "manager":
      return "/portfolio";
    case "stakeholder":
      return "/borrowers";
    case "compliance":
      return "/audit";
    case "admin":
      return "/settings";
    default:
      return "/chat";
  }
}

export function permissionForPath(pathname: string): string | null {
  if (pathname.startsWith("/settings")) return "settings_read";
  if (pathname.startsWith("/audit")) return "audit_read";
  if (pathname.startsWith("/strategy")) return "strategy_read";
  if (pathname.startsWith("/borrowers")) return "borrower";
  if (pathname.startsWith("/portfolio")) return "portfolio_read";
  if (pathname.startsWith("/workflows")) return "workflows";
  if (pathname.startsWith("/documents")) return "documents_read";
  if (pathname.startsWith("/monitoring")) return "strategy_read";
  if (pathname.startsWith("/chat") || pathname === "/") return "chat";
  return null;
}
