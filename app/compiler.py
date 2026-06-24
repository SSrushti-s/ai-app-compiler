from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
import os
from dotenv import load_dotenv
load_dotenv()
# Define the shared memory structure of our compiler
class CompilerState(TypedDict):
    user_prompt: str                 # Raw input text from the user
    intent_ir: Dict[str, Any]         # Stage 1: Extracted Intermediate Representation
    system_design: Dict[str, Any]    # Stage 2: Abstract Architecture Blueprint
    final_schema: Dict[str, Any]     # Stage 3: Code-ready JSON schema
    errors: List[str]                # Tracks any cross-layer sync or validation errors
# --- STAGE NODES ---
# Add this import at the top of compiler.py
from app.utils.gemini_client import generate_intent_and_design

# Replace the two separate nodes with one combined node:
def intent_and_design_node(state: CompilerState) -> Dict[str, Any]:
    print("\n--- Running Stage 1+2: Intent Extraction & System Design ---")
    result = generate_intent_and_design(state["user_prompt"])
    
    # Validate both parts exist
    if "intent_ir" not in result or "system_design" not in result:
        raise ValueError("Combined stage failed to return both intent_ir and system_design")
    
    return {
        "intent_ir": result["intent_ir"],
        "system_design": result["system_design"]
    }
# Add to imports in compiler.py
from app.stages.stage3_schema import generate_schema

# Replace mock node:
def schema_generation_node(state: CompilerState) -> Dict[str, Any]:
    print("\n--- Running Stage 3: Schema Generation ---")
    schema = generate_schema(state["system_design"], state["intent_ir"])
    return {"final_schema": schema}

# Add to imports in compiler.py
from app.stages.stage4_validation import validate_and_repair

# Add this new node:
def validation_node(state: CompilerState) -> Dict[str, Any]:
    print("\n--- Running Stage 4: Validation & Repair ---")
    result = validate_and_repair(state["final_schema"])
    return {
        "final_schema": result["schema"],
        "errors": result["errors"]
    }

# Add to imports
from app.stages.stage5_runtime import simulate_runtime

# Add new node
def runtime_simulation_node(state: CompilerState) -> Dict[str, Any]:
    print("\n--- Running Stage 5: Runtime Simulation ---")
    report = simulate_runtime(state["final_schema"])
    # Add any runtime failures to errors list
    runtime_errors = [f"RUNTIME: {f}" for f in report.get("failures", [])]
    return {
        "errors": state.get("errors", []) + runtime_errors
    }

# --- GRAPH CONSTRUCTION ---
# Initialize the State Machine graph
workflow = StateGraph(CompilerState)
# Register our compiler stages as nodes
workflow.add_node("intent_and_design", intent_and_design_node)
workflow.add_node("schema_generation", schema_generation_node)
# Map out the strict execution flow (Step-by-Step pipeline)
workflow.set_entry_point("intent_and_design")
workflow.add_edge("intent_and_design", "schema_generation")
workflow.add_node("validation", validation_node)
workflow.add_edge("schema_generation", "validation")

workflow.add_node("runtime_simulation", runtime_simulation_node)
workflow.add_edge("validation", "runtime_simulation")
workflow.add_edge("runtime_simulation", END)
compiler_engine = workflow.compile()
if __name__ == "__main__":
    # Test execution with a basic requirement payload
    initial_input = {
        "user_prompt": "Build a CRM with role-based access for Admins and clients.",
        "intent_ir": {},
        "system_design": {},
        "final_schema": {},
        "errors": []
    }

    print("Starting App Compilation Pipeline...")
    output = compiler_engine.invoke(initial_input)
    print("\nCompilation Pipeline Finished Successfully.") 