# AI App Compiler

> Natural language → structured config → validated → executable app schema

A multi-stage AI compiler pipeline that converts plain English app descriptions into complete, validated, executable application schemas including UI, API, database, and auth layers.

**Live Demo:** [your-render-url-here]

---

## What It Does

Input: "Build a CRM with login, contacts, dashboard, role-based access, and premium plan with payments."

Output:
- ✅ DB schema (tables, fields, relations)
- ✅ API schema (endpoints, methods, auth, roles)
- ✅ UI schema (pages, components, route guards)
- ✅ Auth rules (role → permissions mapping)
- ✅ Runtime simulation (SQL migrations, route handlers, React scaffolds)

---

## Architecture

```
User Prompt

↓

Stage 1+2: Intent Extraction & System Design  (1 Gemini API call)

↓

Stage 3:   Schema Generation — DB + API + UI  (2 Gemini API calls)

↓

Stage 4:   Validation & Auto-Repair Engine    (0 API calls — pure logic)

↓

Stage 5:   Runtime Simulation                 (0 API calls — pure logic)

↓

JSON Output + Execution Report
```

### Why Multi-Stage?
Each stage has a single responsibility — like a compiler pass. This means:
- Errors are caught at the right layer
- Individual stages can be retried without rerunning the full pipeline
- Output quality improves as each stage refines the previous one

---

## Pipeline Details

### Stage 1+2 — Intent Extraction & System Design
Parses raw user intent into structured IR (entities, features, roles, constraints), then designs the logical architecture (modules, workflows, API groups, auth strategy). Combined into one API call to reduce latency and quota usage.

### Stage 3 — Schema Generation
Generates three concrete schemas from the architecture:
- **DB schema**: tables, typed fields, relations
- **API schema**: REST endpoints with method, path, auth, roles, request/response shapes
- **UI schema**: pages, components, role-based access guards

Split into 2 focused API calls to stay within token limits and improve reliability.

### Stage 4 — Validation & Repair Engine
Zero API calls. Runs structural and cross-layer consistency checks:
- Pydantic structural validation
- API fields exist in DB tables
- UI roles defined in auth rules
- API roles defined in auth rules
- Valid HTTP methods

Auto-repairs common issues (missing roles, invalid methods, empty tables) without re-running the full pipeline. Retries up to 3 times.

### Stage 5 — Runtime Simulation
Zero API calls. Proves output is executable by simulating:
- SQL `CREATE TABLE` migrations
- Express.js-style route handlers with middleware
- React page scaffolds with component imports
- Auth permission constants

---

## Tech Stack

| Layer | Technology |
|---|---|
| Pipeline Orchestration | LangGraph |
| LLM | Google Gemini 2.5 Flash |
| Schema Validation | Pydantic v2 |
| API Server | FastAPI |
| Frontend | Vanilla HTML/CSS/JS |

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/ai-app-compiler
cd ai-app-compiler
```

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
Create a `.env` file:
GEMINI_API_KEY_1=your_key_here

GEMINI_API_KEY_2=your_key_here

GEMINI_API_KEY_3=your_key_here

### 5. Run the server
```bash
uvicorn app.api:app --reload --port 8000
```

### 6. Open the UI
Visit: http://localhost:8000/ui

---

## API Reference

### `POST /compile`
Runs the full pipeline on a prompt.

**Request:**
```json
{"prompt": "Build a CRM with login and role-based access"}
```

**Response:**
```json
{
  "status": "success",
  "latency_seconds": 45.2,
  "intent_ir": {...},
  "system_design": {...},
  "final_schema": {...},
  "runtime_report": {...},
  "errors": [],
  "assumptions": [...]
}
```

### `GET /health`
Returns `{"status": "ok"}`

---

## Evaluation Framework

Run the full evaluation suite (20 prompts: 10 normal + 10 edge cases):
```bash
python -m app.evaluation.evaluator
```

Tracks: success rate, latency, retry count, failure type per prompt.

---

## Reliability Features

| Problem | Solution |
|---|---|
| Gemini returns wrong JSON types | Pydantic `field_validator` auto-coercion |
| 503 server overload | 3-model × 3-key rotation with backoff |
| 429 quota exhaustion | Automatic key rotation |
| Schema inconsistencies | Stage 4 auto-repair (up to 3 attempts) |
| Vague prompts | Assumption detection + documentation |
| Invalid HTTP methods | Auto-corrected to GET |
| Missing roles | Auto-added with base permissions |

---

## Tradeoffs

| Dimension | Decision | Reason |
|---|---|---|
| Latency vs Quality | 3 API calls per run (~60-120s) | Multi-stage gives better consistency than single prompt |
| Cost vs Reliability | Key rotation across 3 keys | Free tier limits require fallback strategy |
| Strictness vs Flexibility | Pydantic with coercion validators | Pure strictness causes too many false failures |
| Single prompt vs Pipeline | Always pipeline | Spec requirement + better debuggability |