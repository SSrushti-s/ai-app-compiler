# app/api.py

import json
import time ,os
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.compiler import compiler_engine
from app.stages.stage5_runtime import simulate_runtime

app = FastAPI(
    title="AI App Compiler",
    description="Natural language → working app schema",
    version="1.0.0"
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/ui")
def ui():
    return FileResponse("app/static/index.html")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Request/Response Models ---
class CompileRequest(BaseModel):
    prompt: str

class CompileResponse(BaseModel):
    status: str
    latency_seconds: float
    intent_ir: Dict[str, Any]
    system_design: Dict[str, Any]
    final_schema: Dict[str, Any]
    runtime_report: Dict[str, Any]
    errors: List[str]
    assumptions: List[str]


# --- Helper: extract assumptions from vague prompts ---
def extract_assumptions(prompt: str, intent_ir: dict) -> List[str]:
    assumptions = []
    p = prompt.lower()

    if "login" not in p and "auth" not in p:
        assumptions.append("Assumed authentication is required (standard for most apps).")
    if "role" not in p and "admin" not in p:
        assumptions.append("Assumed basic Admin/User role separation.")
    if "payment" not in p and "premium" not in p:
        assumptions.append("No payment system included (not mentioned in prompt).")
    if len(prompt.split()) < 8:
        assumptions.append("Prompt was vague — applied standard CRUD app defaults.")
    if "database" not in p and "db" not in p:
        assumptions.append("Assumed relational database (standard default).")

    return assumptions


# --- Routes ---

@app.get("/")
def root():
    return {
        "message": "AI App Compiler is running.",
        "usage": "POST /compile with {\"prompt\": \"your app description\"}"
    }


# Replace the compile_app function signature:
@app.post("/compile", response_model=CompileResponse)
async def compile_app(request: CompileRequest):
    if not request.prompt or len(request.prompt.strip()) < 3:
        raise HTTPException(status_code=400, detail="Prompt is too short or empty.")

    start = time.time()

    try:
        initial_input = {
            "user_prompt": request.prompt.strip(),
            "intent_ir": {},
            "system_design": {},
            "final_schema": {},
            "errors": []
        }

        # Run in threadpool so async server doesn't block
        output = await run_in_threadpool(compiler_engine.invoke, initial_input)
        latency = round(time.time() - start, 2)

        runtime_report = await run_in_threadpool(simulate_runtime, output["final_schema"])
        assumptions = extract_assumptions(request.prompt, output["intent_ir"])

        return CompileResponse(
            status="success" if not output["errors"] else "partial",
            latency_seconds=latency,
            intent_ir=output["intent_ir"],
            system_design=output["system_design"],
            final_schema=output["final_schema"],
            runtime_report=runtime_report,
            errors=output["errors"],
            assumptions=assumptions
        )

    except Exception as e:
        latency = round(time.time() - start, 2)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "latency_seconds": latency,
                "message": "Pipeline failed. Check logs for details."
            }
        )

@app.get("/debug-keys")
def debug_keys():
    result = {}
    for i in range(1, 11):
        key = os.getenv(f"GEMINI_API_KEY{i}")
        result[f"KEY_{i}"] = "SET" if key else "NOT SET"
    result["GEMINI_API_KEY"] = "SET" if os.getenv("GEMINI_API_KEY") else "NOT SET"
    result["total_found"] = sum(1 for v in result.values() if v == "SET")
    return result

@app.get("/health")
def health():
    return {"status": "ok"}