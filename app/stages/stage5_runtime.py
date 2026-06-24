# app/stages/stage5_runtime.py

import json
from typing import Dict, Any, List

def simulate_runtime(final_schema: dict) -> Dict[str, Any]:
    """
    Simulates executing the schema as if a real app runtime consumed it.
    Checks every piece of output is actually usable to generate a working app.
    Returns a report of what would be generated.
    """
    report = {
        "status": "success",
        "generated": [],
        "warnings": [],
        "failures": []
    }

    db_tables = final_schema.get("db_tables", {})
    api_endpoints = final_schema.get("api_endpoints", [])
    ui_pages = final_schema.get("ui_pages", [])
    auth_rules = final_schema.get("auth_rules", {})

    # --- Simulate DB Migration generation ---
    print("\n  [RUNTIME] Simulating DB migrations...")
    for table_name, table_data in db_tables.items():
        fields = table_data.get("fields", [])
        if not fields:
            report["failures"].append(f"DB: Cannot generate migration for '{table_name}' — no fields.")
            report["status"] = "partial"
            continue

        # Build a simulated SQL CREATE statement
        col_defs = []
        for f in fields:
            sql_type = {
                "string": "VARCHAR(255)",
                "integer": "INTEGER",
                "boolean": "BOOLEAN",
                "datetime": "TIMESTAMP",
                "text": "TEXT",
                "float": "FLOAT"
            }.get(f["type"].lower(), "TEXT")

            constraints = "NOT NULL" if f.get("required") else "NULL"
            unique = "UNIQUE" if f.get("unique") else ""
            col_defs.append(f"  {f['name']} {sql_type} {constraints} {unique}".strip())

        sql = f"CREATE TABLE {table_name} (\n" + ",\n".join(col_defs) + "\n);"
        report["generated"].append({
            "type": "db_migration",
            "table": table_name,
            "sql": sql
        })
        print(f"    ✓ Migration ready: {table_name}")

    # --- Simulate API Route generation ---
    print("\n  [RUNTIME] Simulating API routes...")
    for ep in api_endpoints:
        method = ep.get("method", "")
        path = ep.get("path", "")
        auth = ep.get("auth_required", False)
        roles = ep.get("roles", [])

        if not method or not path:
            report["failures"].append(f"API: Endpoint missing method or path — skipping.")
            report["status"] = "partial"
            continue

        # Simulate route handler code
        middleware = "auth_middleware, " if auth else ""
        role_check = f"require_roles({roles}), " if roles else ""
        route_code = (
            f"router.{method.lower()}('{path}', {middleware}{role_check}handler)"
        )

        report["generated"].append({
            "type": "api_route",
            "method": method,
            "path": path,
            "code": route_code
        })
        print(f"    ✓ Route ready: {method} {path}")

    # --- Simulate UI Page generation ---
    print("\n  [RUNTIME] Simulating UI pages...")
    for page in ui_pages:
        name = page.get("name", "")
        route = page.get("route", "")
        components = page.get("components", [])
        roles = page.get("roles", [])

        if not route:
            report["warnings"].append(f"UI: Page '{name}' has no route defined.")
            continue

        # Simulate a React page scaffold
        component_imports = "\n".join(
            [f"import {c} from '../components/{c}';" for c in components]
        )
        role_guard = f"// Access: {', '.join(roles)}" if roles else ""
        page_code = (
            f"{component_imports}\n\n"
            f"{role_guard}\n"
            f"export default function {name.replace(' ', '')}Page() {{\n"
            f"  return <div>{' '.join([f'<{c} />' for c in components])}</div>;\n"
            f"}}"
        )

        report["generated"].append({
            "type": "ui_page",
            "name": name,
            "route": route,
            "code": page_code
        })
        print(f"    ✓ Page ready: {name} ({route})")

    # --- Simulate Auth Middleware generation ---
    print("\n  [RUNTIME] Simulating auth middleware...")
    for role, permissions in auth_rules.items():
        report["generated"].append({
            "type": "auth_middleware",
            "role": role,
            "permissions": permissions,
            "code": f"const {role.lower()}Permissions = {json.dumps(permissions)};"
        })
        print(f"    ✓ Auth config ready: {role} ({len(permissions)} permissions)")

    # --- Final summary ---
    total = len(report["generated"])
    failures = len(report["failures"])
    warnings = len(report["warnings"])

    print(f"\n  [RUNTIME] Summary: {total} artifacts generated, "
          f"{failures} failures, {warnings} warnings.")

    if failures > 0:
        report["status"] = "partial"
    if total == 0:
        report["status"] = "failed"

    return report


if __name__ == "__main__":
    # Load a sample schema to test
    sample_schema = {
        "db_tables": {
            "User": {
                "fields": [
                    {"name": "id", "type": "integer", "required": True, "unique": True},
                    {"name": "email", "type": "string", "required": True, "unique": True},
                    {"name": "password", "type": "string", "required": True, "unique": False},
                    {"name": "role", "type": "string", "required": True, "unique": False}
                ],
                "relations": ["has_many: Contact"]
            },
            "Contact": {
                "fields": [
                    {"name": "id", "type": "integer", "required": True, "unique": True},
                    {"name": "name", "type": "string", "required": True, "unique": False},
                    {"name": "email", "type": "string", "required": False, "unique": False},
                    {"name": "user_id", "type": "integer", "required": True, "unique": False}
                ],
                "relations": ["belongs_to: User"]
            }
        },
        "api_endpoints": [
            {
                "method": "POST",
                "path": "/api/auth/login",
                "description": "User login",
                "auth_required": False,
                "roles": [],
                "request_body": {"email": "string", "password": "string"},
                "response_fields": {"token": "string", "user": "object"}
            },
            {
                "method": "GET",
                "path": "/api/contacts",
                "description": "Get all contacts",
                "auth_required": True,
                "roles": ["Admin", "User"],
                "request_body": {},
                "response_fields": {"contacts": "array"}
            }
        ],
        "ui_pages": [
            {
                "name": "Login Page",
                "route": "/login",
                "components": ["LoginForm", "Navbar"],
                "roles": ["Anonymous"]
            },
            {
                "name": "Contacts Page",
                "route": "/contacts",
                "components": ["ContactTable", "SearchBar"],
                "roles": ["Admin", "User"]
            }
        ],
        "auth_rules": {
            "Admin": ["contacts:read", "contacts:write", "contacts:delete"],
            "User": ["contacts:read", "contacts:write"],
            "Anonymous": ["auth:login", "auth:register"]
        }
    }

    result = simulate_runtime(sample_schema)
    print("\n--- Runtime Simulation Report ---")
    print(json.dumps(result, indent=2))