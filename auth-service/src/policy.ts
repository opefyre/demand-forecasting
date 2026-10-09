export const roles = ["admin", "planner", "approver", "viewer"] as const;
export type Role = (typeof roles)[number];
export const scopeLabels: Record<string, string> = {
  "reports:read": "Read approved forecasts",
  "reports:export": "Export approved forecasts",
  "drafts:read": "Read forecast drafts",
  "releases:approve": "Approve forecasts",
  "inputs:read": "Read sales history",
  "inputs:write": "Update sales history",
  "customers:read": "Read customers",
  "customers:write": "Update customers",
  "orders:read": "Read orders",
  "orders:write": "Update orders",
  "factors:read": "Read forecast factors",
  "factors:write": "Update forecast factors",
  "forecasts:run": "Run forecasts",
  "forecasts:write": "Manage forecast drafts",
  "connections:read": "Read connections",
  "connections:sync": "Refresh connections",
  "connections:manage": "Manage connections",
  "settings:manage": "Manage settings",
  "members:manage": "Manage people",
  "audit:read": "Read access history",
  "ai:query": "Ask the assistant",
  "ai:actions": "Run assistant workflows",
  "chats:own": "Manage own chats",
  "views:own": "Manage own views",
};
export const permissions = {
  viewer: [
    "reports:read",
    "reports:export",
    "ai:query",
    "chats:own",
    "views:own",
  ],
  approver: [
    "reports:read",
    "reports:export",
    "drafts:read",
    "releases:approve",
    "ai:query",
    "chats:own",
    "views:own",
  ],
  planner: [
    "reports:read",
    "reports:export",
    "drafts:read",
    "inputs:read",
    "inputs:write",
    "customers:read",
    "customers:write",
    "orders:read",
    "orders:write",
    "factors:read",
    "factors:write",
    "forecasts:run",
    "forecasts:write",
    "connections:read",
    "connections:sync",
    "ai:query",
    "ai:actions",
    "chats:own",
    "views:own",
  ],
  admin: [
    "reports:read",
    "reports:export",
    "drafts:read",
    "inputs:read",
    "inputs:write",
    "customers:read",
    "customers:write",
    "orders:read",
    "orders:write",
    "factors:read",
    "factors:write",
    "forecasts:run",
    "forecasts:write",
    "releases:approve",
    "connections:read",
    "connections:sync",
    "connections:manage",
    "settings:manage",
    "members:manage",
    "audit:read",
    "ai:query",
    "ai:actions",
    "chats:own",
    "views:own",
  ],
} satisfies Record<Role, string[]>;

export function asRole(value: unknown): Role {
  if (!roles.includes(value as Role)) throw new Error("Invalid role");
  return value as Role;
}

export function keyScopes(
  role: Role,
  requested: unknown,
  companyKey = false,
): string[] {
  if (
    !Array.isArray(requested) ||
    requested.length === 0 ||
    requested.some((v) => typeof v !== "string")
  )
    throw new Error("Select API permissions");
  // User/key administration always requires an interactive session, never a key.
  const blocked = new Set(
    companyKey
      ? [
          "members:manage",
          "settings:manage",
          "releases:approve",
          "chats:own",
          "views:own",
        ]
      : ["members:manage"],
  );
  if (
    requested.some(
      (scope) => !permissions[role].includes(scope) || blocked.has(scope),
    )
  )
    throw new Error("API permissions exceed the allowed role");
  return [...new Set(requested)].sort();
}

export function effectiveScopes(
  role: Role,
  keyPermissions: string[],
): string[] {
  return keyPermissions.filter((scope) => permissions[role].includes(scope));
}
