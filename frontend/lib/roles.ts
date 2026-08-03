export type Role = "analyst" | "manager" | "admin";

export const ROLE_LABELS: Record<Role, string> = {
  analyst: "Collection Analyst",
  manager: "Operational Manager",
  admin: "Admin",
};

export const ROLE_PERMISSIONS: Record<Role, Set<string>> = {
  analyst: new Set(["chat", "borrower", "strategy_read", "documents_read"]),
  manager: new Set([
    "chat",
    "borrower",
    "portfolio_read",
    "strategy_read",
    "strategy_run",
    "workflows",
    "workflows_approve",
    "audit_read",
    "audit_export",
    "documents_read",
    "executive_read",
    "monitoring_read",
  ]),
  admin: new Set([
    "chat",
    "borrower",
    "portfolio_read",
    "strategy_read",
    "strategy_run",
    "workflows",
    "workflows_approve",
    "audit_read",
    "audit_export",
    "settings_read",
    "settings_write",
    "documents_read",
    "executive_read",
    "monitoring_read",
  ]),
};

const LEGACY_ROLE_MAP: Record<string, Role> = {
  stakeholder: "manager",
  compliance: "manager",
  executive: "manager",
};

export function normalizeRole(role: string): Role {
  const mapped = LEGACY_ROLE_MAP[role] || role;
  if (mapped in ROLE_LABELS) return mapped as Role;
  return "analyst";
}

export function canAccess(role: Role, permission: string): boolean {
  return ROLE_PERMISSIONS[role]?.has(permission) ?? false;
}

export function canSeeNav(role: Role, navKey: string): boolean {
  const map: Record<string, string> = {
    assistant: "chat",
    workspace: "borrower",
    optimization: "strategy_read",
    portfolio: "portfolio_read",
    approvals: "workflows",
    executive: "executive_read",
    documents: "documents_read",
    monitoring: "monitoring_read",
    audit: "audit_read",
    settings: "settings_read",
  };
  return canAccess(role, map[navKey] || navKey);
}

export function homePathForRole(role: Role): string {
  switch (role) {
    case "manager":
      return "/approvals";
    case "admin":
      return "/settings";
    default:
      return "/workspace";
  }
}

export function permissionForPath(pathname: string): string | null {
  if (pathname.startsWith("/settings")) return "settings_read";
  if (pathname.startsWith("/audit")) return "audit_read";
  if (pathname.startsWith("/optimization") || pathname.startsWith("/strategy")) return "strategy_read";
  if (pathname.startsWith("/workspace") || pathname.startsWith("/borrowers")) return "borrower";
  if (pathname.startsWith("/portfolio")) return "portfolio_read";
  if (pathname.startsWith("/approvals") || pathname.startsWith("/workflows")) return "workflows";
  if (pathname.startsWith("/executive")) return "executive_read";
  if (pathname.startsWith("/documents")) return "documents_read";
  if (pathname.startsWith("/monitoring")) return "monitoring_read";
  if (pathname.startsWith("/assistant") || pathname.startsWith("/chat") || pathname === "/") return "chat";
  return null;
}
