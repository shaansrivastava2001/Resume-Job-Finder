import json
import logging
import os
import time
from typing import Any

from ollama import Client

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:latest")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "180"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
RANK_BATCH_SIZE = int(os.getenv("RANK_BATCH_SIZE", "6"))

_client = Client(host=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT)
log = logging.getLogger("resume-jobs")


PROFILE_SYSTEM = """You extract structured candidate profiles from resume text.
Return ONLY valid JSON matching this schema (no prose, no markdown fences):
{
  "current_title": string,
  "seniority": "intern" | "junior" | "mid" | "senior" | "staff" | "principal" | "lead" | "manager" | "director" | "unknown",
  "years_experience": number,
  "top_skills": string[],
  "preferred_roles": string[],
  "summary": string
}
preferred_roles must be 3-5 concrete job-search keywords (e.g. "Senior Backend Engineer", "ML Platform Engineer").
If the user provides preferences (target seniority, role types, industries, anything else), they OVERRIDE
the resume's defaults — reflect them directly in preferred_roles. For example, if the resume reads as senior
but the user says "also open to mid-level Software Engineer", include both seniorities in preferred_roles
(e.g. "Senior Backend Engineer", "Software Engineer", "Backend Engineer"). User intent wins over resume signal.
"""


RANK_SYSTEM = """You rank job postings against a candidate profile.
For each job, return a match score 0-100 and a one-sentence reason.
Return ONLY valid JSON of the form:
{ "rankings": [ { "id": string, "score": number, "reason": string } ] }
No prose, no markdown fences. Score on skill overlap, seniority fit, and stated preferences.
"""


def extract_profile(
    resume_text: str,
    preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    user_content: dict[str, Any] = {"resume": resume_text[:15000]}
    if preferences:
        trimmed = {k: v for k, v in preferences.items() if v not in (None, "", False)}
        if trimmed:
            user_content["user_preferences"] = trimmed

    resp = _client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": PROFILE_SYSTEM},
            {"role": "user", "content": json.dumps(user_content)},
        ],
        format="json",
        options={"temperature": 0.1, "num_ctx": OLLAMA_NUM_CTX},
    )
    return json.loads(resp["message"]["content"])


def _rank_batch(
    profile: dict[str, Any],
    preferences: dict[str, Any],
    jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    compact_jobs = [
        {
            "id": j["id"],
            "title": j.get("title", ""),
            "company": j.get("company", ""),
            "location": j.get("location", ""),
            "is_remote": j.get("is_remote"),
            "salary": j.get("salary", ""),
            "description": (j.get("description") or "")[:600],
        }
        for j in jobs
    ]

    user_payload = {
        "profile": profile,
        "preferences": preferences,
        "jobs": compact_jobs,
    }

    resp = _client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": RANK_SYSTEM},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        format="json",
        options={"temperature": 0.1, "num_ctx": OLLAMA_NUM_CTX},
    )
    parsed = json.loads(resp["message"]["content"])
    return parsed.get("rankings", [])


def rank_jobs(
    profile: dict[str, Any],
    preferences: dict[str, Any],
    jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not jobs:
        return []

    rankings: list[dict[str, Any]] = []
    batch_size = max(1, RANK_BATCH_SIZE)
    total_batches = (len(jobs) + batch_size - 1) // batch_size

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i : i + batch_size]
        batch_idx = i // batch_size + 1
        t0 = time.perf_counter()
        try:
            batch_rankings = _rank_batch(profile, preferences, batch)
        except Exception as e:
            log.exception("rank batch %d/%d failed; assigning fallback scores", batch_idx, total_batches)
            batch_rankings = [
                {"id": j["id"], "score": 50, "reason": "Ranking unavailable for this batch."}
                for j in batch
            ]
        log.info(
            "ranked batch %d/%d (%d jobs) in %.1fs",
            batch_idx,
            total_batches,
            len(batch),
            time.perf_counter() - t0,
        )
        rankings.extend(batch_rankings)

    return rankings
