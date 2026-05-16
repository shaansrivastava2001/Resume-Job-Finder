import math
from typing import Any

import pandas as pd
from jobspy import scrape_jobs


DEFAULT_SITES = ["indeed", "linkedin", "zip_recruiter", "google"]


def search_jobs(
    search_terms: list[str],
    location: str | None,
    is_remote: bool,
    results_per_term: int = 15,
    sites: list[str] | None = None,
    country_indeed: str = "USA",
) -> list[dict[str, Any]]:
    """Run JobSpy across multiple search terms and merge results."""
    sites = sites or DEFAULT_SITES
    frames: list[pd.DataFrame] = []

    for term in search_terms:
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=term,
                location=location or "",
                is_remote=is_remote,
                results_wanted=results_per_term,
                hours_old=168,
                country_indeed=country_indeed,
                google_search_term=f"{term} jobs near {location}" if location else f"{term} jobs",
            )
            if df is not None and not df.empty:
                df["search_term"] = term
                frames.append(df)
        except Exception as e:
            print(f"[jobspy] search '{term}' failed: {e}")
            continue

    if not frames:
        return []

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["job_url"], keep="first")
    return _normalize(merged)


def _normalize(df: pd.DataFrame) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        out.append(
            {
                "id": f"job_{idx}",
                "title": _clean(row.get("title")),
                "company": _clean(row.get("company")),
                "location": _clean(row.get("location")),
                "is_remote": bool(row.get("is_remote")) if not _is_nan(row.get("is_remote")) else None,
                "salary": _format_salary(row),
                "site": _clean(row.get("site")),
                "url": _clean(row.get("job_url")),
                "description": _clean(row.get("description")),
                "date_posted": _clean(row.get("date_posted")),
                "search_term": _clean(row.get("search_term")),
            }
        )
    return out


def _clean(value: Any) -> str | None:
    if _is_nan(value):
        return None
    if value is None:
        return None
    return str(value).strip()


def _is_nan(value: Any) -> bool:
    if value is None:
        return True
    try:
        return isinstance(value, float) and math.isnan(value)
    except Exception:
        return False


def _format_salary(row: pd.Series) -> str | None:
    lo = row.get("min_amount")
    hi = row.get("max_amount")
    interval = row.get("interval")
    currency = row.get("currency") or ""

    if _is_nan(lo) and _is_nan(hi):
        return None

    parts: list[str] = []
    if not _is_nan(lo) and not _is_nan(hi):
        parts.append(f"{currency}{int(lo):,} - {currency}{int(hi):,}".strip())
    elif not _is_nan(lo):
        parts.append(f"from {currency}{int(lo):,}".strip())
    elif not _is_nan(hi):
        parts.append(f"up to {currency}{int(hi):,}".strip())

    if interval and not _is_nan(interval):
        parts.append(f"/ {interval}")
    return " ".join(parts) or None
