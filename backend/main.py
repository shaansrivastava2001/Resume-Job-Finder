import json
import logging
import time
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from jobs import search_jobs
from llm import extract_profile, rank_jobs
from resume_parser import UnsupportedResumeFormat, extract_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("JobSpy").setLevel(logging.WARNING)
log = logging.getLogger("resume-jobs")

app = FastAPI(title="Resume-Based Job Finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    client = request.client.host if request.client else "?"
    log.info("→ %s %s from %s", request.method, request.url.path, client)
    try:
        response = await call_next(request)
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        log.exception("✗ %s %s failed after %.0fms", request.method, request.url.path, elapsed)
        raise
    elapsed = (time.perf_counter() - start) * 1000
    log.info(
        "← %s %s %d in %.0fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


class JobMatch(BaseModel):
    id: str
    title: str | None
    company: str | None
    location: str | None
    is_remote: bool | None
    salary: str | None
    site: str | None
    url: str | None
    date_posted: str | None
    score: int
    reason: str


class SearchResponse(BaseModel):
    profile: dict[str, Any]
    matches: list[JobMatch]
    total_jobs_found: int


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse)
async def search(
    resume: UploadFile = File(...),
    expected_salary: str = Form(""),
    location: str = Form(""),
    remote: str = Form("false"),
    country: str = Form("USA"),
    extra_preferences: str = Form(""),
) -> SearchResponse:
    log.info(
        "search request: file=%s salary=%r location=%r country=%r remote=%s extra=%r",
        resume.filename,
        expected_salary,
        location,
        country,
        remote,
        extra_preferences[:80] + ("…" if len(extra_preferences) > 80 else ""),
    )

    try:
        raw = await resume.read()
        resume_text = extract_text(resume.filename or "resume", raw)
    except UnsupportedResumeFormat as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("resume parse failed")
        raise HTTPException(status_code=400, detail=f"Failed to read resume: {e}")

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Resume appears to be empty.")
    log.info("parsed resume: %d chars extracted from %s", len(resume_text), resume.filename)

    preferences = {
        "expected_salary": expected_salary,
        "location": location,
        "remote": remote.lower() == "true",
        "extra": extra_preferences,
    }

    try:
        t0 = time.perf_counter()
        profile = extract_profile(resume_text, preferences=preferences)
        log.info(
            "profile extracted in %.1fs: title=%r seniority=%r years=%s skills=%d preferred_roles=%s",
            time.perf_counter() - t0,
            profile.get("current_title"),
            profile.get("seniority"),
            profile.get("years_experience"),
            len(profile.get("top_skills") or []),
            profile.get("preferred_roles"),
        )
    except Exception as e:
        log.exception("profile extraction failed")
        raise HTTPException(status_code=502, detail=f"Ollama profile extraction failed: {e}")

    search_terms = profile.get("preferred_roles") or [profile.get("current_title", "Software Engineer")]
    search_terms = [t for t in search_terms if t][:4]
    if not search_terms:
        search_terms = ["Software Engineer"]

    log.info("searching jobs: terms=%s location=%r remote=%s", search_terms, location, preferences["remote"])
    t0 = time.perf_counter()
    jobs = search_jobs(
        search_terms=search_terms,
        location=location,
        is_remote=preferences["remote"],
        country_indeed=country,
    )
    by_site: dict[str, int] = {}
    for j in jobs:
        site = j.get("site") or "unknown"
        by_site[site] = by_site.get(site, 0) + 1
    log.info(
        "scraped %d unique jobs in %.1fs (by site: %s)",
        len(jobs),
        time.perf_counter() - t0,
        ", ".join(f"{s}={n}" for s, n in by_site.items()) or "none",
    )

    if not jobs:
        return SearchResponse(profile=profile, matches=[], total_jobs_found=0)

    try:
        t0 = time.perf_counter()
        rankings = rank_jobs(profile, preferences, jobs)
        log.info("ranked %d jobs in %.1fs", len(rankings), time.perf_counter() - t0)
    except Exception as e:
        log.exception("ranking failed; returning unranked jobs")
        rankings = [{"id": j["id"], "score": 50, "reason": "Ranking unavailable."} for j in jobs]

    score_by_id = {r["id"]: r for r in rankings}
    matches: list[JobMatch] = []
    for j in jobs:
        r = score_by_id.get(j["id"], {"score": 0, "reason": "No ranking returned."})
        matches.append(
            JobMatch(
                id=j["id"],
                title=j.get("title"),
                company=j.get("company"),
                location=j.get("location"),
                is_remote=j.get("is_remote"),
                salary=j.get("salary"),
                site=j.get("site"),
                url=j.get("url"),
                date_posted=j.get("date_posted"),
                score=int(r.get("score", 0)),
                reason=str(r.get("reason", "")),
            )
        )

    matches.sort(key=lambda m: (m.score, m.date_posted or ""), reverse=True)
    top_preview = ", ".join(f"{m.title}@{m.score}" for m in matches[:3]) or "none"
    log.info("returning %d matches; top: %s", len(matches), top_preview)
    return SearchResponse(profile=profile, matches=matches, total_jobs_found=len(jobs))
