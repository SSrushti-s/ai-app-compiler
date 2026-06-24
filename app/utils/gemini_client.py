# app/utils/gemini_client.py

import os, time
from google import genai
from dotenv import load_dotenv
load_dotenv()

API_KEYS = [
    os.getenv("GEMINI_API_KEY1"),
    os.getenv("GEMINI_API_KEY2"),
    os.getenv("GEMINI_API_KEY3"),
    os.getenv("GEMINI_API_KEY4"),
    os.getenv("GEMINI_API_KEY5"),
    os.getenv("GEMINI_API_KEY6"),
    os.getenv("GEMINI_API_KEY7"),
    os.getenv("GEMINI_API_KEY8"),
    os.getenv("GEMINI_API_KEY9"),
    os.getenv("GEMINI_API_KEY10"),
]

MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",  # lightest model, least likely to be overloaded
]

def generate_with_fallback(prompt: str) -> str:
    """Try each model x each key. On 503, wait longer before next attempt."""
    attempts = []
    for model in MODELS:
        for i, key in enumerate(API_KEYS):
            if not key:
                continue
            attempts.append((model, key, i+1))

    for idx, (model, key, key_num) in enumerate(attempts):
        try:
            print(f"  → Trying model={model}, key={key_num}...")
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            err = str(e)
            if "503" in err:
                wait = 30 if idx < 3 else 60
                print(f"  503 overload. Waiting {wait}s before next attempt...")
                time.sleep(wait)
            elif "429" in err:
                print(f"  429 quota on key {key_num}. Switching...")
                time.sleep(10)
            else:
                print(f"  Unexpected error: {e}")
                time.sleep(5)

    raise RuntimeError("All models and keys exhausted. Try again in a few minutes.")

# Add this to app/utils/gemini_client.py

COMBINED_STAGE_1_2_PROMPT = """
You are a senior software architect AI.

Given this app requirement, do TWO things in one response:

1. Extract structured intent (intent_ir)
2. Design the system architecture (system_design)

Return ONLY a valid JSON object with exactly 2 keys: "intent_ir" and "system_design".

intent_ir must have:
- entities: list of main data objects
- features: list of functional features  
- roles: list of user roles
- relationships: list of entity relationships
- constraints: list of business rules

system_design must have:
- modules: list of system modules
- workflows: list of key workflows
- api_groups: list of API groups
- auth_strategy: string describing auth approach
- data_flows: list of data flow descriptions

Requirement: {user_prompt}
"""

def generate_intent_and_design(user_prompt: str) -> dict:
    """Combines Stage 1 + Stage 2 into a single API call."""
    import json
    from pydantic import BaseModel, field_validator
    from typing import List

    class IntentIR(BaseModel):
        entities: List[str]
        features: List[str]
        roles: List[str]
        relationships: List[str]
        constraints: List[str]

        @field_validator("entities", "features", "roles", "relationships", "constraints", mode="before")
        @classmethod
        def coerce_to_strings(cls, v):
            if isinstance(v, list):
                result = []
                for item in v:
                    if isinstance(item, dict):
                        result.append(
                            item.get("name") or
                            item.get("description") or
                            str(list(item.values())[0])
                        )
                    else:
                        result.append(str(item))
                return result
            return v

    class SystemDesign(BaseModel):
        modules: List[str]
        workflows: List[str]
        api_groups: List[str]
        auth_strategy: str
        data_flows: List[str]

        @field_validator("modules", "workflows", "api_groups", "data_flows", mode="before")
        @classmethod
        def coerce_to_strings(cls, v):
            if isinstance(v, list):
                result = []
                for item in v:
                    if isinstance(item, dict):
                        result.append(
                            item.get("name") or
                            item.get("description") or
                            str(list(item.values())[0])
                        )
                    else:
                        result.append(str(item))
                return result
            return v

    prompt = COMBINED_STAGE_1_2_PROMPT.format(user_prompt=user_prompt)
    raw = generate_with_fallback(prompt)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    parsed = json.loads(raw)

    # Validate and coerce both parts
    ir = IntentIR(**parsed["intent_ir"]).model_dump()
    design = SystemDesign(**parsed["system_design"]).model_dump()

    return {"intent_ir": ir, "system_design": design}