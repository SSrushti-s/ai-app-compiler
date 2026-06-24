# app/stages/stage4_validation.py

import json
from typing import Dict, Any, List
from pydantic import ValidationError, errors
from app.stages.stage3_schema import AppSchema, DBTable, APIEndpoint, UIPage

# ------------------------------------------------------------------ #
#  VALIDATOR                                                           #
# ------------------------------------------------------------------ #

def validate_schema(final_schema: dict) -> List[str]:
    """
    Returns a list of error strings.
    Empty list = schema is valid.
    """
    errors = []

    # 1. Pydantic structural validation
    try:
        AppSchema(**final_schema)
    except ValidationError as e:
        for err in e.errors():
            errors.append(f"STRUCTURE: {err['loc']} — {err['msg']}")
        return errors  # no point doing deeper checks if structure is broken

    # 2. Cross-layer consistency checks
    db_tables = final_schema.get("db_tables", {})
    api_endpoints = final_schema.get("api_endpoints", [])
    ui_pages = final_schema.get("ui_pages", [])
    auth_rules = final_schema.get("auth_rules", {})

    # Collect all DB field names across all tables
    all_db_fields = {}
    for table_name, table_data in db_tables.items():
        all_db_fields[table_name] = [f["name"] for f in table_data.get("fields", [])]

    # Check: every API endpoint with a request_body references real DB fields
    EXEMPT_FIELDS = {
    "password", "token", "refresh_token", "access_token",
    "confirm_password", "old_password", "new_password",
    "page", "limit", "offset", "sort", "filter", "search"
    }

    for ep in api_endpoints:
        for field in ep.get("request_body", {}).keys():
            if field in EXEMPT_FIELDS:
                continue
            # Skip fields that are clearly metadata types not stored in DB
            if field in ("required", "optional", "type", "format"):
                continue
            matched = any(field in fields for fields in all_db_fields.values())
            if not matched:
                errors.append(
                    f"CROSS_LAYER: API endpoint '{ep['path']}' uses field '{field}' "
                    f"not found in any DB table."
                )

    # Check: every role in UI pages exists in auth_rules
    defined_roles = set(auth_rules.keys())
    for page in ui_pages:
        for role in page.get("roles", []):
            if role not in defined_roles and role != "Anonymous":
                errors.append(
                    f"CROSS_LAYER: UI page '{page['name']}' references undefined role '{role}'."
                )

    # Check: every role in API endpoints exists in auth_rules
    for ep in api_endpoints:
        for role in ep.get("roles", []):
            if role not in defined_roles:
                errors.append(
                    f"CROSS_LAYER: API endpoint '{ep['path']}' references undefined role '{role}'."
                )

    # Check: required fields present in all DB tables
    for table_name, table_data in db_tables.items():
        if not table_data.get("fields"):
            errors.append(f"DB: Table '{table_name}' has no fields defined.")

    # Check: all API endpoints have valid HTTP methods
    valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH"}
    for ep in api_endpoints:
        if ep.get("method", "").upper() not in valid_methods:
            errors.append(
                f"API: Endpoint '{ep['path']}' has invalid method '{ep['method']}'."
            )

    return errors


# ------------------------------------------------------------------ #
#  REPAIRER                                                            #
# ------------------------------------------------------------------ #

def repair_schema(final_schema: dict, errors: List[str]) -> dict:
    """
    Attempts to auto-repair common issues without re-running the full pipeline.
    Returns the repaired schema.
    """
    schema = json.loads(json.dumps(final_schema))  # deep copy

    for error in errors:

        # Fix: undefined role in auth_rules
        if "references undefined role" in error:
            # Extract the role name from the error message
            role = error.split("undefined role '")[1].rstrip("'.")
            if role not in schema.get("auth_rules", {}):
                print(f"  [REPAIR] Adding missing role '{role}' to auth_rules.")
                schema["auth_rules"][role] = ["auth:login", "auth:logout"]

        # Fix: missing fields in DB table
        if "has no fields defined" in error:
            table = error.split("Table '")[1].split("'")[0]
            print(f"  [REPAIR] Adding default 'id' field to table '{table}'.")
            schema["db_tables"][table]["fields"] = [
                {"name": "id", "type": "integer", "required": True, "unique": True},
                {"name": "created_at", "type": "datetime", "required": True, "unique": False}
            ]

        # Fix: invalid HTTP method
        if "has invalid method" in error:
            path = error.split("Endpoint '")[1].split("'")[0]
            for ep in schema["api_endpoints"]:
                if ep["path"] == path:
                    print(f"  [REPAIR] Fixing invalid method on '{path}' → defaulting to GET.")
                    ep["method"] = "GET"

    return schema


# ------------------------------------------------------------------ #
#  MAIN VALIDATION + REPAIR LOOP                                       #
# ------------------------------------------------------------------ #

def validate_and_repair(final_schema: dict, max_attempts: int = 3) -> Dict[str, Any]:
    """
    Runs validation, attempts repair, re-validates.
    Returns dict with repaired schema + error log.
    """
    schema = final_schema
    all_errors = []

    for attempt in range(max_attempts):
        print(f"\n  [VALIDATION] Attempt {attempt + 1}...")
        errors = validate_schema(schema)

        if not errors:
            print(f"  [VALIDATION] ✓ Schema is valid.")
            return {"schema": schema, "errors": [], "attempts": attempt + 1}

        print(f"  [VALIDATION] Found {len(errors)} issue(s):")
        for e in errors:
            print(f"    - {e}")

        all_errors.extend(errors)

        if attempt < max_attempts - 1:
            print(f"  [REPAIR] Attempting auto-repair...")
            schema = repair_schema(schema, errors)
        else:
            print(f"  [VALIDATION] Max attempts reached. Returning best schema with known errors.")

    return {"schema": schema, "errors": all_errors, "attempts": max_attempts}


if __name__ == "__main__":
    # Test with a deliberately broken schema
    broken_schema = {
        "db_tables": {
            "User": {
                "fields": [
                    {"name": "id", "type": "integer", "required": True, "unique": True},
                    {"name": "email", "type": "string", "required": True, "unique": True}
                ],
                "relations": []
            }
        },
        "api_endpoints": [
            {
                "method": "FETCH",  # invalid method
                "path": "/api/users",
                "description": "Get all users",
                "auth_required": True,
                "roles": ["SuperAdmin"],  # undefined role
                "request_body": {},
                "response_fields": {"users": "array"}
            }
        ],
        "ui_pages": [
            {
                "name": "Home",
                "route": "/",
                "components": ["Navbar"],
                "roles": ["SuperAdmin"]  # undefined role
            }
        ],
        "auth_rules": {
            "Admin": ["auth:login"],
            "User": ["auth:login"]
        }
    }

    result = validate_and_repair(broken_schema)
    print("\nFinal result:")
    print(json.dumps(result, indent=2))