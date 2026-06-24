# app/stages/stage3_schema.py

import json
from pydantic import BaseModel
from typing import List, Dict
from app.utils.gemini_client import generate_with_fallback
from pydantic import BaseModel, field_validator
from typing import List, Dict, Union

class DBField(BaseModel):
    name: str
    type: str
    required: bool
    unique: bool = False

class DBTable(BaseModel):
    fields: List[DBField] = []
    relations: List[str] = []

    @field_validator("fields", "relations", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v):
        return v if v is not None else []
# In stage3_schema.py — replace the APIEndpoint class with this:

class APIEndpoint(BaseModel):
    method: str
    path: str
    description: str
    auth_required: bool
    roles: List[str] = []
    request_body: Dict[str, str] = {}
    response_fields: Dict[str, str] = {}

    @field_validator("request_body", "response_fields", mode="before")
    @classmethod
    def coerce_to_dict(cls, v):
        # Handle None (GET endpoints have no body)
        if v is None:
            return {}
        # Handle list of dicts — convert to flat dict
        if isinstance(v, list):
            result = {}
            for item in v:
                if isinstance(item, dict):
                    for key, val in item.items():
                        result[str(key)] = str(val)
            return result
        return v

    @field_validator("roles", mode="before")
    @classmethod
    def coerce_roles(cls, v):
        if v is None:
            return []
        return v
    
class UIPage(BaseModel):
    name: str
    route: str
    components: List[str] = []
    roles: List[str] = []

    @field_validator("components", "roles", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v):
        return v if v is not None else []

class AppSchema(BaseModel):
    db_tables: Dict[str, DBTable]
    api_endpoints: List[APIEndpoint]
    ui_pages: List[UIPage]
    auth_rules: Dict[str, List[str]]

# --- Split into 2 smaller prompts ---

DB_API_PROMPT = """
You are a backend architect. Given these entities and API groups, generate ONLY the database tables and API endpoints.

Return ONLY valid JSON with exactly 2 keys:
- db_tables: object where each key is a table name, value has:
    - fields: list of {{name, type, required, unique}}
    - relations: list of relation strings
- api_endpoints: list of objects each with:
    - method, path, description, auth_required, roles, request_body, response_fields

Entities: {entities}
Roles: {roles}
API groups: {api_groups}
Auth strategy: {auth_strategy}
"""

UI_AUTH_PROMPT = """
You are a frontend architect. Given these modules and roles, generate ONLY the UI pages and auth rules.

Return ONLY valid JSON with exactly 2 keys:
- ui_pages: list of objects each with:
    - name, route, components, roles
- auth_rules: object where each key is a role name, value is list of allowed actions

Modules: {modules}
Roles: {roles}
Workflows: {workflows}
"""

def generate_schema(system_design: dict, intent_ir: dict) -> dict:
    # Call 1: DB + API (smaller, focused)
    prompt1 = DB_API_PROMPT.format(
        entities=json.dumps(intent_ir.get("entities", [])  ),
        roles=json.dumps(intent_ir.get("roles", [])),
        api_groups=json.dumps(system_design.get("api_groups", [])),
        auth_strategy=system_design.get("auth_strategy", "")
    )
    raw1 = generate_with_fallback(prompt1)
    if raw1.startswith("```"):
        raw1 = raw1.split("```")[1]
        if raw1.startswith("json"):
            raw1 = raw1[4:]
    part1 = json.loads(raw1.strip())

    # Call 2: UI + Auth rules (smaller, focused)
    prompt2 = UI_AUTH_PROMPT.format(
        modules=json.dumps(system_design.get("modules", [])),
        roles=json.dumps(intent_ir.get("roles", [])),
        workflows=json.dumps(system_design.get("workflows", []))
    )
    raw2 = generate_with_fallback(prompt2)
    if raw2.startswith("```"):
        raw2 = raw2.split("```")[1]
        if raw2.startswith("json"):
            raw2 = raw2[4:]
    part2 = json.loads(raw2.strip())

    # Merge both parts
    merged = {**part1, **part2}
    validated = AppSchema(**merged)
    return validated.model_dump()


if __name__ == "__main__":
    from app.stages.stage1_intent import extract_intent
    from app.stages.stage2_design import generate_system_design
    test_prompt = "Build a CRM with login, contacts, dashboard, role-based access, and premium plan with payments. Admins can see analytics."
    ir = extract_intent(test_prompt)
    design = generate_system_design(ir)
    result = generate_schema(design, ir)
    print(json.dumps(result, indent=2))