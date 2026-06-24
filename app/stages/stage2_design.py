# app/stages/stage2_design.py

import json
from pydantic import BaseModel
from typing import List
from app.utils.gemini_client import generate_with_fallback

class SystemDesign(BaseModel):
    modules: List[str]
    workflows: List[str]
    api_groups: List[str]
    auth_strategy: str
    data_flows: List[str]

DESIGN_PROMPT = """
You are a senior software architect. Given this structured intent IR, design a logical system architecture.

Return ONLY a valid JSON object. No explanation, no markdown, no code blocks.
The JSON must have exactly these keys:
- modules: list of system modules needed
- workflows: list of key user/system workflows as plain strings
- api_groups: list of API groups needed
- auth_strategy: single string describing the auth approach
- data_flows: list of data flow descriptions

Intent IR:
{intent_ir}
"""

def generate_system_design(intent_ir: dict) -> dict:
    prompt = DESIGN_PROMPT.format(intent_ir=json.dumps(intent_ir, indent=2))
    raw = generate_with_fallback(prompt)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    parsed = json.loads(raw)
    validated = SystemDesign(**parsed)
    return validated.model_dump()


if __name__ == "__main__":
    from app.stages.stage1_intent import extract_intent
    test_prompt = "Build a CRM with login, contacts, dashboard, role-based access, and premium plan with payments. Admins can see analytics."
    ir = extract_intent(test_prompt)
    result = generate_system_design(ir)
    print(json.dumps(result, indent=2))