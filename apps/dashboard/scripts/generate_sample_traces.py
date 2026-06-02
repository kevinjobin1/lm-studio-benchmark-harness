#!/usr/bin/env python3
"""Generate realistic sample execution traces for dashboard development.

Creates individual trace_*.json files in public/traces/ that match
the TraceData schema expected by loadTraces.ts, plus runs
generate_traces_index.py to produce the index manifest.

Usage:
    python3 scripts/generate_sample_traces.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


# ── Trace step templates ──────────────────────────────────────────

def _step(
    sid: str,
    stype: str,
    label: str,
    timing_ms: int,
    detail: str = "",
    tool: str = "",
    input_val: str = "",
    output_val: str = "",
    status: str = "success",
) -> dict:
    s: dict = {
        "id": sid,
        "type": stype,
        "label": label,
        "timing_ms": timing_ms,
        "status": status,
    }
    if detail:
        s["detail"] = detail
    if tool:
        s["tool"] = tool
    if input_val:
        s["input"] = input_val
    if output_val:
        s["output"] = output_val
    return s


# ── Scenario builders — each returns (prompt, steps, response, metrics_overrides) ──

def nestjs_jwt_guard(model: str) -> tuple:
    """Build a JWT guard for NestJS — multi-step tool-call trace."""
    prompt = (
        "Implement a JWT authentication guard for a NestJS controller. "
        "The guard should validate the JWT from the Authorization header, "
        "extract the user payload, and attach it to the request context. "
        "Use Passport strategy with @nestjs/passport."
    )
    steps = [
        _step(f"{model}-s0", "system", "System Instruction", 0,
              detail="You are an expert TypeScript developer. Provide complete, production-ready code."),
        _step(f"{model}-s1", "prompt", "Prompt Received", 5,
              detail=prompt[:120]),
        _step(f"{model}-s2", "token", "Token: 'Implement'", 2),
        _step(f"{model}-s3", "token", "Token: 'a'", 1),
        _step(f"{model}-s4", "token", "Token: 'JWT'", 3),
        _step(f"{model}-s5", "reasoning", "Analyzing requirements", 120,
              detail="Need: JwtStrategy, JwtGuard, AuthModule. Use passport-jwt for token extraction."),
        _step(f"{model}-s6", "tool_call", "Calling: read_file auth.module.ts", 85,
              tool="file_read", input_val="auth.module.ts",
              output_val="Existing auth module with basic Passport setup. No guard implemented."),
        _step(f"{model}-s7", "tool_call", "Calling: read_file jwt.strategy.ts", 45,
              tool="file_read", input_val="jwt.strategy.ts",
              output_val="Partial JwtStrategy — validate() returns empty payload."),
        _step(f"{model}-s8", "reasoning", "Planning implementation", 200,
              detail="1) Complete JwtStrategy.validate() to return user object. 2) Create JwtAuthGuard extending AuthGuard('jwt'). 3) Add @UseGuards decorator."),
        _step(f"{model}-s9", "tool_call", "Calling: write_file jwt.strategy.ts", 350,
              tool="file_write", input_val="jwt.strategy.ts",
              output_val="Wrote 42 lines. Completed validate() with user extraction from payload."),
        _step(f"{model}-s10", "tool_call", "Calling: write_file jwt-auth.guard.ts", 180,
              tool="file_write", input_val="jwt-auth.guard.ts",
              output_val="Wrote 18 lines. JwtAuthGuard extending AuthGuard('jwt')."),
        _step(f"{model}-s11", "reasoning", "Verifying integration", 90,
              detail="Guard uses Passport's built-in JWT validation. No circular deps. Exported from AuthModule."),
        _step(f"{model}-s12", "response", "Generated Implementation", 280,
              detail="Created JwtAuthGuard with Passport strategy — validates token, extracts user, attaches to request."),
    ]
    response = (
        "import { Injectable } from '@nestjs/common';\n"
        "import { AuthGuard } from '@nestjs/passport';\n\n"
        "@Injectable()\n"
        "export class JwtAuthGuard extends AuthGuard('jwt') {}\n"
    )
    metrics_overrides = {"tokens_per_second": 42, "ttft_ms": 210, "total_latency_ms": 1360}
    return prompt, steps, response, metrics_overrides


def react_form_component(model: str) -> tuple:
    """Add a controlled form component to a React app."""
    prompt = (
        "Create a controlled form component in React with TypeScript for user registration. "
        "Fields: email, password (with confirmation), display name. "
        "Include client-side validation, error messages, and a submit handler "
        "that calls an async API function. Use React hooks."
    )
    steps = [
        _step(f"{model}-s0", "system", "System Instruction", 0,
              detail="You are an expert React developer. Write clean, typed, accessible components."),
        _step(f"{model}-s1", "prompt", "Prompt Received", 5,
              detail=prompt[:120]),
        _step(f"{model}-s2", "token", "Token: 'Create'", 2),
        _step(f"{model}-s3", "token", "Token: 'a'", 1),
        _step(f"{model}-s4", "token", "Token: 'controlled'", 2),
        _step(f"{model}-s5", "reasoning", "Planning component structure", 150,
              detail="Need: state for each field, validation logic, error display, async submit. Use useState + useCallback."),
        _step(f"{model}-s6", "tool_call", "Calling: read_file src/components/", 60,
              tool="file_search", input_val="src/components/",
              output_val="Found: LoginForm.tsx, Dashboard.tsx. No registration form exists."),
        _step(f"{model}-s7", "tool_call", "Calling: read_file src/api/auth.ts", 40,
              tool="file_read", input_val="src/api/auth.ts",
              output_val="export async function registerUser(data: RegisterPayload): Promise<User> — existing API helper."),
        _step(f"{model}-s8", "reasoning", "Designing validation", 100,
              detail="Email: regex validation. Password: min 8 chars, must match confirmation. Display name: required, min 2 chars."),
        _step(f"{model}-s9", "tool_call", "Calling: write_file RegisterForm.tsx", 250,
              tool="file_write", input_val="src/components/RegisterForm.tsx",
              output_val="Wrote 95 lines. Controlled form with useForm hook, validation errors, async submit."),
        _step(f"{model}-s10", "response", "Generated Implementation", 180,
              detail="Created RegisterForm component with email, password, confirmation, display name fields + validation."),
    ]
    response = (
        "import React, { useState, useCallback } from 'react';\n\n"
        "interface RegisterFormData {\n"
        "  email: string;\n"
        "  password: string;\n"
        "  confirmPassword: string;\n"
        "  displayName: string;\n"
        "}\n"
        "// ... full component with validation and error display\n"
    )
    metrics_overrides = {"tokens_per_second": 55, "ttft_ms": 180, "total_latency_ms": 790}
    return prompt, steps, response, metrics_overrides


def debug_race_condition(model: str) -> tuple:
    """Debug a race condition in a TypeScript async handler."""
    prompt = (
        "Debug this race condition: two concurrent API calls update shared state, "
        "causing the second update to overwrite the first. The code is in "
        "src/services/dataSync.ts. Fix the issue with proper async coordination."
    )
    steps = [
        _step(f"{model}-s0", "system", "System Instruction", 0,
              detail="You are an expert debugger. Identify root causes precisely and provide minimal fixes."),
        _step(f"{model}-s1", "prompt", "Prompt Received", 5,
              detail=prompt[:120]),
        _step(f"{model}-s2", "token", "Token: 'Debug'", 2),
        _step(f"{model}-s3", "token", "Token: 'this'", 1),
        _step(f"{model}-s4", "token", "Token: 'race'", 2),
        _step(f"{model}-s5", "tool_call", "Calling: read_file dataSync.ts", 55,
              tool="file_read", input_val="src/services/dataSync.ts",
              output_val="Found race: fetchA() and fetchB() both write to sharedCache without coordination."),
        _step(f"{model}-s6", "reasoning", "Analyzing race condition", 200,
              detail="fetchA() completes → writes cache. fetchB() completes later → overwrites cache with stale partial data. Root cause: no sequencing or merge strategy."),
        _step(f"{model}-s7", "tool_call", "Calling: search for sharedCache usage", 40,
              tool="grep", input_val="sharedCache",
              output_val="3 usages in dataSync.ts, 1 in cacheUtils.ts. All unprotected."),
        _step(f"{model}-s8", "reasoning", "Designing fix", 150,
              detail="Option A: Promise.all + merge. Option B: Sequential execution. Option C: Mutex. Recommend A with deep merge for minimal perf impact."),
        _step(f"{model}-s9", "tool_call", "Calling: write_file dataSync.ts", 300,
              tool="file_write", input_val="src/services/dataSync.ts",
              output_val="Replaced racy write pattern with Promise.all + structured merge. Added 12 lines."),
        _step(f"{model}-s10", "response", "Fix Applied", 160,
              detail="Resolved race condition using Promise.all + deep merge. fetchA and fetchB now run concurrently, results are merged atomically."),
    ]
    response = (
        "// Before: racy writes\n"
        "// const dataA = await fetchA(); sharedCache = { ...sharedCache, ...dataA };\n"
        "// const dataB = await fetchB(); sharedCache = { ...sharedCache, ...dataB };\n\n"
        "// After: atomic merge\n"
        "const [dataA, dataB] = await Promise.all([fetchA(), fetchB()]);\n"
        "sharedCache = deepMerge(sharedCache, dataA, dataB);\n"
    )
    metrics_overrides = {"tokens_per_second": 38, "ttft_ms": 160, "total_latency_ms": 910}
    return prompt, steps, response, metrics_overrides


def api_integration_test(model: str) -> tuple:
    """Write integration tests for a REST API endpoint."""
    prompt = (
        "Write integration tests for the GET /api/users endpoint. "
        "Test: pagination, filtering by role, empty results, "
        "authorization header validation, and error response format. "
        "Use supertest with Jest."
    )
    steps = [
        _step(f"{model}-s0", "system", "System Instruction", 0,
              detail="You are an expert QA engineer. Write thorough, maintainable integration tests."),
        _step(f"{model}-s1", "prompt", "Prompt Received", 5,
              detail=prompt[:120]),
        _step(f"{model}-s2", "reasoning", "Identifying test cases", 130,
              detail="1) GET /api/users returns 200 + paginated array. 2) ?role=admin filters correctly. 3) Empty results returns 200 + []. 4) No auth header returns 401. 5) Error cases return {error, message} format."),
        _step(f"{model}-s3", "tool_call", "Calling: read_file users.controller.ts", 50,
              tool="file_read", input_val="src/users/users.controller.ts",
              output_val="GET /api/users with @Query() pagination and role filter. Uses JwtAuthGuard."),
        _step(f"{model}-s4", "tool_call", "Calling: read_file users.service.ts", 35,
              tool="file_read", input_val="src/users/users.service.ts",
              output_val="findAll(pagination, roleFilter) → Promise<PaginatedResult<User>>."),
        _step(f"{model}-s5", "reasoning", "Structuring test file", 80,
              detail="Use describe blocks for each scenario. beforeEach seeds test data. afterEach cleans up."),
        _step(f"{model}-s6", "tool_call", "Calling: write_file users.integration.test.ts", 420,
              tool="file_write", input_val="src/users/users.integration.test.ts",
              output_val="Wrote 130 lines. 8 test cases covering pagination, filtering, auth, error handling."),
        _step(f"{model}-s7", "response", "Tests Generated", 200,
              detail="Created 8 integration tests using supertest — pagination, role filter, empty results, auth validation, error format checks."),
    ]
    response = (
        "import request from 'supertest';\n"
        "import { app } from '../app';\n\n"
        "describe('GET /api/users', () => {\n"
        "  it('returns paginated users with 200', async () => {\n"
        "    const res = await request(app).get('/api/users?page=1&limit=10');\n"
        "    expect(res.status).toBe(200);\n"
        "    expect(res.body.data).toBeInstanceOf(Array);\n"
        "    expect(res.body.meta).toHaveProperty('total');\n"
        "  });\n"
        "  // ... more tests\n"
        "});\n"
    )
    metrics_overrides = {"tokens_per_second": 48, "ttft_ms": 195, "total_latency_ms": 920}
    return prompt, steps, response, metrics_overrides


def failed_schema_migration(model: str) -> tuple:
    """Generate a failed trace — schema migration that hit an error."""
    prompt = (
        "Migrate the User schema to add a 'preferences' JSONB column "
        "with a default value of '{}'. Update the Prisma schema and "
        "generate the migration."
    )
    steps = [
        _step(f"{model}-s0", "system", "System Instruction", 0,
              detail="You are a backend developer. Write database migrations safely."),
        _step(f"{model}-s1", "prompt", "Prompt Received", 5,
              detail=prompt[:120]),
        _step(f"{model}-s2", "reasoning", "Planning migration", 80,
              detail="Need: ALTER TABLE users ADD COLUMN preferences JSONB DEFAULT '{}' NOT NULL."),
        _step(f"{model}-s3", "tool_call", "Calling: read_file schema.prisma", 45,
              tool="file_read", input_val="prisma/schema.prisma",
              output_val="model User { id Int, email String, name String } — no preferences field yet."),
        _step(f"{model}-s4", "tool_call", "Calling: write_file schema.prisma", 120,
              tool="file_write", input_val="prisma/schema.prisma",
              output_val="Added 'preferences Json @default(\"{}\")' to User model."),
        _step(f"{model}-s5", "tool_call", "Calling: npx prisma migrate dev", 850,
              tool="shell_exec", input_val="npx prisma migrate dev --name add-preferences",
              output_val="Error: column 'preferences' of relation 'User' already exists"),
        _step(f"{model}-s6", "error", "Migration Failed", 500,
              detail="Error: column 'preferences' of relation 'User' already exists. The column was manually added and Prisma can't reconcile the drift.",
              status="failure"),
        _step(f"{model}-s7", "reasoning", "Diagnosing failure", 200,
              detail="Someone manually ran ALTER TABLE outside Prisma. Need to: 1) Create baseline migration. 2) Or drop and recreate column via Prisma."),
        _step(f"{model}-s8", "error", "Drift Resolution Failed", 100,
              detail="Unable to resolve schema drift automatically. Manual intervention required.",
              status="failure"),
    ]
    response = ""
    metrics_overrides = {"tokens_per_second": 0, "ttft_ms": 210, "total_latency_ms": 2100, "completion_tokens": 0}
    return prompt, steps, response, metrics_overrides


# ── Trace generator ───────────────────────────────────────────────

def build_trace(
    trace_id: str,
    run_id: str,
    model: str,
    pack: str,
    timestamp: str,
    prompt: str,
    steps: list,
    response: str,
    metrics_overrides: dict,
    status: str = "completed",
) -> dict:
    """Assemble a complete TraceData-compatible dict."""
    total_time = sum(s["timing_ms"] for s in steps)
    prompt_tok = len(prompt) // 4
    comp_tok = len(response) // 4 if response else 0
    total_tok = prompt_tok + comp_tok

    base_metrics = {
        "ttft_ms": 180,
        "tokens_per_second": 45,
        "total_tokens": total_tok,
        "prompt_tokens": prompt_tok,
        "completion_tokens": comp_tok,
        "total_latency_ms": total_time,
        "memory_pressure_mb": 850,
        "token_timings_ms": [s["timing_ms"] for s in steps if s["type"] == "token"],
    }
    base_metrics.update(metrics_overrides)

    return {
        "trace_id": trace_id,
        "run_id": run_id,
        "model": model,
        "provider": "lm-studio",
        "prompt": prompt,
        "system_prompt": None,
        "pack": pack,
        "timestamp": timestamp,
        "totalTimeMs": total_time,
        "status": status,
        "steps": steps,
        "metrics": base_metrics,
        "artifacts": {
            "response": response,
            "logs": [f"[{timestamp}] Trace {trace_id} captured"],
            "errors": [s["detail"] for s in steps if s["status"] == "failure"],
        },
        "hardware": {
            "platform": "macOS 15.6.1",
            "processor": "Apple M3 Pro",
            "memory_gb": 18,
            "architecture": "arm64",
        },
    }


# ── Main ──────────────────────────────────────────────────────────

def main():
    output_dir = Path("public/traces")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Base timestamp — spread traces across recent time
    base_ts = datetime(2026, 6, 2, 10, 0, 0)

    scenarios = [
        # (model, pack, builder_fn, status_override)
        ("google/gemma-4-e4b", "nestjs-pack", nestjs_jwt_guard, "completed"),
        ("google/gemma-4-e4b", "react-pack", react_form_component, "completed"),
        ("google/gemma-4-e4b", "debugging-pack", debug_race_condition, "completed"),
        ("google/gemma-4-e4b", "nestjs-pack", api_integration_test, "completed"),
        ("google/gemma-4-e4b", "react-pack", failed_schema_migration, "failed"),
        ("lfm2.5-8b-a1b", "nestjs-pack", nestjs_jwt_guard, "completed"),
        ("lfm2.5-8b-a1b", "react-pack", react_form_component, "completed"),
        ("lfm2.5-8b-a1b", "debugging-pack", debug_race_condition, "completed"),
        ("lfm2.5-8b-a1b", "nestjs-pack", api_integration_test, "completed"),
        ("lfm2.5-8b-a1b", "react-pack", failed_schema_migration, "failed"),
    ]

    traces_written = 0
    for i, (model, pack, builder, status) in enumerate(scenarios):
        model_slug = model.replace("/", "_").replace(".", "_")
        trace_id = f"trace_{model_slug}_{pack}_{i:02d}"
        run_id = f"run_{model_slug}_{i:02d}"
        timestamp = (base_ts + timedelta(minutes=i * 15)).strftime("%Y-%m-%dT%H:%M:%SZ")

        prompt, steps, response, metrics_overrides = builder(trace_id)
        trace = build_trace(
            trace_id=trace_id,
            run_id=run_id,
            model=model,
            pack=pack,
            timestamp=timestamp,
            prompt=prompt,
            steps=steps,
            response=response,
            metrics_overrides=metrics_overrides,
            status=status,
        )

        filepath = output_dir / f"{trace_id}.json"
        with open(filepath, "w") as f:
            json.dump(trace, f, indent=2, default=str)

        print(f"  ✓ {filepath.name}  ({model} · {pack} · {status} · {len(steps)} steps · {trace['totalTimeMs']}ms)")
        traces_written += 1

    print(f"\n✓ Wrote {traces_written} trace files to {output_dir}/")

    # Now generate the index
    print("\n📋 Generating trace index...")
    index_script = Path("scripts/generate_traces_index.py")
    if index_script.exists():
        result = subprocess.run(
            [sys.executable, str(index_script), "--traces-dir", "public/traces", "--output", "public/traces/index.json", "--cwd", "."],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
    else:
        print("  ⚠ generate_traces_index.py not found — skipping index generation.")


if __name__ == "__main__":
    main()
