# app/evaluation/evaluator.py

import json
import time
from typing import Dict, Any, List
from dataclasses import dataclass, field

@dataclass
class EvalResult:
    prompt: str
    category: str           # "normal" or "edge_case"
    success: bool
    attempts: int
    latency_seconds: float
    failure_type: str = ""  # "validation", "api_error", "json_parse", "runtime"
    errors: List[str] = field(default_factory=list)
    artifacts_generated: int = 0

def run_single_eval(prompt: str, category: str, compiler_engine) -> EvalResult:
    """Run one prompt through the full pipeline and record metrics."""
    start = time.time()
    try:
        initial_input = {
            "user_prompt": prompt,
            "intent_ir": {},
            "system_design": {},
            "final_schema": {},
            "errors": []
        }
        output = compiler_engine.invoke(initial_input)
        latency = time.time() - start

        errors = output.get("errors", [])
        schema = output.get("final_schema", {})
        artifacts = (
            len(schema.get("db_tables", {})) +
            len(schema.get("api_endpoints", [])) +
            len(schema.get("ui_pages", [])) +
            len(schema.get("auth_rules", {}))
        )

        return EvalResult(
            prompt=prompt,
            category=category,
            success=len(errors) == 0,
            attempts=1,
            latency_seconds=round(latency, 2),
            errors=errors,
            artifacts_generated=artifacts
        )

    except Exception as e:
        latency = time.time() - start
        err = str(e)

        # Classify failure type
        if "json" in err.lower() or "parse" in err.lower():
            failure_type = "json_parse"
        elif "503" in err or "429" in err:
            failure_type = "api_error"
        elif "validation" in err.lower():
            failure_type = "validation"
        else:
            failure_type = "runtime"

        return EvalResult(
            prompt=prompt,
            category=category,
            success=False,
            attempts=1,
            latency_seconds=round(latency, 2),
            failure_type=failure_type,
            errors=[err]
        )


def run_evaluation(compiler_engine) -> Dict[str, Any]:
    """
    Runs 20 prompts (10 normal + 10 edge cases) through the pipeline.
    Returns full metrics report.
    """

    normal_prompts = [
        ("Build a CRM with login, contacts, dashboard, role-based access, and premium plan with payments. Admins can see analytics.", "normal"),
        ("Create a task management app with projects, tasks, subtasks, deadlines, and team collaboration.", "normal"),
        ("Build an e-commerce store with product listings, cart, checkout, payments, and order tracking.", "normal"),
        ("Create a blog platform with posts, comments, categories, tags, and admin moderation.", "normal"),
        ("Build a HR management system with employees, departments, leave requests, and payroll.", "normal"),
        ("Create a school management system with students, teachers, classes, grades, and attendance.", "normal"),
        ("Build a hospital management system with patients, doctors, appointments, and billing.", "normal"),
        ("Create a real estate platform with property listings, agents, inquiries, and virtual tours.", "normal"),
        ("Build a food delivery app with restaurants, menus, orders, delivery tracking, and payments.", "normal"),
        ("Create an inventory management system with products, suppliers, stock levels, and purchase orders.", "normal"),
    ]

    edge_case_prompts = [
        ("Build an app.", "edge_case"),                                          # too vague
        ("Create something for my business.", "edge_case"),                      # extremely vague
        ("Build a CRM but also a social network and also a game.", "edge_case"), # conflicting/overloaded
        ("Make an app with login but no users.", "edge_case"),                   # logically inconsistent
        ("Build a payment system with no authentication.", "edge_case"),         # missing constraint
        ("Create an admin dashboard with no admin role.", "edge_case"),          # role conflict
        ("Build a real-time chat app with offline-first sync and blockchain auth and AI recommendations.", "edge_case"),  # overspecified
        ("Make an app exactly like Facebook but better.", "edge_case"),          # vague + unrealistic
        ("Build a system where all users are admins.", "edge_case"),             # constraint conflict
        ("Create an e-commerce app with free checkout and no payment gateway.", "edge_case"),  # logical gap
    ]

    all_prompts = normal_prompts + edge_case_prompts
    results: List[EvalResult] = []

    print(f"\n{'='*60}")
    print(f"  EVALUATION FRAMEWORK — {len(all_prompts)} prompts")
    print(f"{'='*60}\n")

    for i, (prompt, category) in enumerate(all_prompts):
        print(f"[{i+1}/{len(all_prompts)}] {category.upper()}: {prompt[:60]}...")
        result = run_single_eval(prompt, category, compiler_engine)
        results.append(result)
        status = "✓ PASS" if result.success else f"✗ FAIL ({result.failure_type})"
        print(f"  {status} | {result.latency_seconds}s | {result.artifacts_generated} artifacts\n")
        time.sleep(3)  # avoid hammering the API between runs

    # --- Compute metrics ---
    total = len(results)
    normal_results = [r for r in results if r.category == "normal"]
    edge_results = [r for r in results if r.category == "edge_case"]

    def success_rate(subset): 
        return round(len([r for r in subset if r.success]) / len(subset) * 100, 1) if subset else 0

    def avg_latency(subset):
        return round(sum(r.latency_seconds for r in subset) / len(subset), 2) if subset else 0

    def failure_breakdown(subset):
        types = {}
        for r in subset:
            if not r.success:
                types[r.failure_type] = types.get(r.failure_type, 0) + 1
        return types

    report = {
        "summary": {
            "total_prompts": total,
            "overall_success_rate": f"{success_rate(results)}%",
            "normal_success_rate": f"{success_rate(normal_results)}%",
            "edge_case_success_rate": f"{success_rate(edge_results)}%",
            "avg_latency_normal": f"{avg_latency(normal_results)}s",
            "avg_latency_edge": f"{avg_latency(edge_results)}s",
            "failure_types": failure_breakdown(results)
        },
        "results": [
            {
                "prompt": r.prompt[:80],
                "category": r.category,
                "success": r.success,
                "latency": f"{r.latency_seconds}s",
                "artifacts": r.artifacts_generated,
                "failure_type": r.failure_type,
                "errors": r.errors[:2]  # only first 2 errors for brevity
            }
            for r in results
        ]
    }

    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  Overall success rate : {report['summary']['overall_success_rate']}")
    print(f"  Normal prompts       : {report['summary']['normal_success_rate']}")
    print(f"  Edge cases           : {report['summary']['edge_case_success_rate']}")
    print(f"  Avg latency (normal) : {report['summary']['avg_latency_normal']}")
    print(f"  Avg latency (edge)   : {report['summary']['avg_latency_edge']}")
    print(f"  Failure breakdown    : {report['summary']['failure_types']}")

    return report


if __name__ == "__main__":
    # Import and run the compiled pipeline
    import sys
    sys.path.append(".")
    from app.compiler import compiler_engine

    report = run_evaluation(compiler_engine)

    # Save report to file
    with open("evaluation_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\n  Report saved to evaluation_report.json")