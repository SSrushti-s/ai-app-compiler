# app/stages/stage1_intent.py

import os, json
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv
from app.utils.groq_client import generate_with_fallback
load_dotenv()

class IntentIR(BaseModel):
    entities: List[str]
    features: List[str]
    roles: List[str]
    relationships: List[str]
    constraints: List[str]

INTENT_PROMPT = """
You are a software architect AI. Analyze the user's requirement and extract a structured intent.

Return ONLY a valid JSON object. No explanation, no markdown, no code blocks.
The JSON must have exactly these keys:
- entities: list of main data objects/actors
- features: list of functional features
- roles: list of user roles
- relationships: list of relationships between entities
- constraints: list of business rules or access constraints

Requirement: {user_prompt}
"""

def extract_intent(user_prompt: str) -> dict:
    prompt = INTENT_PROMPT.format(user_prompt=user_prompt)
    raw = generate_with_fallback(prompt)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    parsed = json.loads(raw)
    validated = IntentIR(**parsed)
    return validated.model_dump()


if __name__ == "__main__":
    test_prompt = "Build a CRM with login, contacts, dashboard, role-based access, and premium plan with payments. Admins can see analytics."
    result = extract_intent(test_prompt)
    print(json.dumps(result, indent=2))