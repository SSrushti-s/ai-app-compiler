# app/utils/gemini_client.py

import os
import time
import json
from groq import Groq
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator
from typing import List
load_dotenv()

MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
]

import re

def extract_json(raw: str) -> str:
    """Pull the outermost {...} JSON object out of a model response,
    regardless of code fences or stray text around it."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?", "", raw, flags=re.IGNORECASE).strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model output. Raw (first 300 chars): {raw[:300]!r}")
    return match.group(0)
    
def get_groq_clients():
    """Read all 7 Groq keys fresh every call."""
    clients = []
    for i in range(1, 8):
        key = os.getenv(f"GROQ_API_KEY{i}")
        if key and key.strip():
            clients.append((i, key.strip()))
    print(f"  [CLIENT] Found {len(clients)} Groq key(s).")
    return clients

def generate_with_fallback(prompt: str) -> str:
    """Try each model x each Groq key. Log exact errors."""

    keys = get_groq_clients()

    if not keys:
        raise RuntimeError(
            "No GROQ keys found. Set GROQ_API_KEY1 through GROQ_API_KEY7."
        )

    attempts = []

    for model in MODELS:
        for key_num, key in keys:
            attempts.append((model, key, key_num))

    last_error = None

    for idx, (model, key, key_num) in enumerate(attempts):
        try:
            print(
                f"  → Trying model={model}, key={key_num}, "
                f"attempt={idx + 1}/{len(attempts)}..."
            )

            client = Groq(api_key=key)

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=6000
            )

            content = response.choices[0].message.content

            if not content:
                raise RuntimeError("Groq returned empty content")

            print(f"  ✓ Success: model={model}, key={key_num}")

            return content.strip()

        except Exception as e:
            last_error = e

            print(
                f"  ✗ FAILED: model={model}, key={key_num}"
            )
            print(f"  ✗ ERROR TYPE: {type(e).__name__}")
            print(f"  ✗ ERROR DETAILS: {repr(e)}")

            time.sleep(1)

    raise RuntimeError(
        f"All Groq attempts failed. Last error: {repr(last_error)}"
    )
# --- Combined Stage 1+2 Prompt ---

COMBINED_STAGE_1_2_PROMPT = """
You are a senior software architect AI.

Given this app requirement, do TWO things in one response:

1. Extract structured intent (intent_ir)
2. Design the system architecture (system_design)

Return ONLY a valid JSON object with exactly 2 keys: "intent_ir" and "system_design".

intent_ir must have:
- entities: list of main data objects (plain strings only)
- features: list of functional features (plain strings only)
- roles: list of user roles (plain strings only)
- relationships: list of entity relationships (plain strings only)
- constraints: list of business rules (plain strings only)

system_design must have:
- modules: list of system modules (plain strings only)
- workflows: list of key workflows (plain strings only)
- api_groups: list of API groups (plain strings only)
- auth_strategy: single string describing auth approach
- data_flows: list of data flow descriptions (plain strings only)

IMPORTANT: Every list must contain plain strings only, never objects or dicts.

Requirement: {user_prompt}
"""


# --- Pydantic Models ---

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


def generate_intent_and_design(user_prompt: str) -> dict:
    """Combines Stage 1 + Stage 2 into a single Groq API call."""
    prompt = COMBINED_STAGE_1_2_PROMPT.format(user_prompt=user_prompt)
    raw = generate_with_fallback(prompt)

    try:
        parsed = json.loads(extract_json(raw))
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Stage1+2 combined call returned invalid JSON: {e}\nRaw (first 500 chars): {raw[:500]!r}")
    ir = IntentIR(**parsed["intent_ir"]).model_dump()
    design = SystemDesign(**parsed["system_design"]).model_dump()

    return {"intent_ir": ir, "system_design": design}
