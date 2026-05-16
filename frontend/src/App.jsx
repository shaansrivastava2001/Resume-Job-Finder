import { useMemo, useRef, useState } from "react";

const COUNTRIES = [
  "USA", "UK", "Canada", "Australia", "India", "Germany",
  "France", "Netherlands", "Singapore", "Spain", "Italy",
];

const PAGE_SIZE = 8;

export default function App() {
  const [file, setFile] = useState(null);
  const [salary, setSalary] = useState("");
  const [location, setLocation] = useState("");
  const [country, setCountry] = useState("USA");
  const [remote, setRemote] = useState(false);
  const [extra, setExtra] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);

    if (!file) {
      setError("Please upload a resume (PDF, DOCX, or TXT).");
      return;
    }

    const fd = new FormData();
    fd.append("resume", file);
    fd.append("expected_salary", salary);
    fd.append("location", location);
    fd.append("country", country);
    fd.append("remote", remote ? "true" : "false");
    fd.append("extra_preferences", extra);

    setLoading(true);
    try {
      const res = await fetch("/api/search", { method: "POST", body: fd });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Request failed (${res.status})`);
      }
      setResult(await res.json());
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <h1>Resume-Based Job Finder</h1>
        <p className="subtitle">
          We match live job postings against your resume.
        </p>
      </header>

      <form onSubmit={onSubmit} className="card">
        <FileDrop file={file} onFile={setFile} />

        <div className="row">
          <label className="field">
            <span>Expected salary</span>
            <input
              type="text"
              placeholder="e.g. $150k or 30 LPA"
              value={salary}
              onChange={(e) => setSalary(e.target.value)}
            />
          </label>

          <label className="field">
            <span>Location</span>
            <input
              type="text"
              placeholder="e.g. New York, NY"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
          </label>
        </div>

        <div className="row">
          <label className="field">
            <span>Country</span>
            <div className="select-wrap">
              <select value={country} onChange={(e) => setCountry(e.target.value)}>
                {COUNTRIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <svg className="select-chevron" viewBox="0 0 12 8" aria-hidden="true">
                <path d="M1 1l5 5 5-5" stroke="currentColor" strokeWidth="1.6"
                  fill="none" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </label>

          <label className="field toggle-field">
            <span>Work mode</span>
            <button
              type="button"
              role="switch"
              aria-checked={remote}
              className={`switch ${remote ? "on" : ""}`}
              onClick={() => setRemote((v) => !v)}
            >
              <span className="switch-knob" />
              <span className="switch-label">{remote ? "Remote only" : "Any"}</span>
            </button>
          </label>
        </div>

        <label className="field">
          <span>Other preferences (optional)</span>
          <textarea
            rows={3}
            placeholder="e.g. avoid finance, prefer Python/Go, open to mid-level roles"
            value={extra}
            onChange={(e) => setExtra(e.target.value)}
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? "Analyzing resume & searching jobs…" : "Find matching jobs"}
        </button>

        {error && <div className="error">{error}</div>}
      </form>

      {result && <Results data={result} />}

      <footer className="site-footer">
        © {new Date().getFullYear()} Shaan Srivastava. All rights reserved.
      </footer>
    </div>
  );
}

function FileDrop({ file, onFile }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const pick = (f) => {
    if (f) onFile(f);
  };

  return (
    <div
      className={`dropzone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        pick(e.dataTransfer.files?.[0]);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        hidden
        onChange={(e) => pick(e.target.files?.[0])}
      />
      <svg className="dropzone-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 16V4m0 0L7 9m5-5l5 5" stroke="currentColor" strokeWidth="1.8"
          fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke="currentColor"
          strokeWidth="1.8" fill="none" strokeLinecap="round" />
      </svg>
      {file ? (
        <div className="dropzone-text">
          <strong>{file.name}</strong>
          <span className="muted">Click or drop another file to replace</span>
        </div>
      ) : (
        <div className="dropzone-text">
          <strong>Upload your resume</strong>
          <span className="muted">Drag &amp; drop or click to browse · PDF, DOCX, TXT</span>
        </div>
      )}
    </div>
  );
}

function Results({ data }) {
  const { profile, matches, total_jobs_found } = data;
  const [page, setPage] = useState(1);

  const totalPages = Math.max(1, Math.ceil(matches.length / PAGE_SIZE));
  const current = Math.min(page, totalPages);
  const pageItems = useMemo(
    () => matches.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE),
    [matches, current]
  );

  return (
    <section className="results">
      <div className="card profile">
        <h2>Your profile</h2>
        <div className="profile-grid">
          <div><strong>Title</strong><span>{profile.current_title || "—"}</span></div>
          <div><strong>Seniority</strong><span>{profile.seniority || "—"}</span></div>
          <div><strong>Years exp</strong><span>{profile.years_experience ?? "—"}</span></div>
          <div className="full">
            <strong>Top skills</strong>
            <span>{(profile.top_skills || []).join(", ") || "—"}</span>
          </div>
          <div className="full">
            <strong>Matched roles</strong>
            <span>{(profile.preferred_roles || []).join(", ") || "—"}</span>
          </div>
        </div>
      </div>

      <h2 className="results-heading">
        {matches.length} ranked matches{" "}
        <span className="muted">(of {total_jobs_found} found)</span>
      </h2>

      {matches.length === 0 && (
        <p className="muted">No jobs returned. Try a broader location or remote.</p>
      )}

      <div className="job-list">
        {pageItems.map((j) => (
          <JobCard key={j.id} job={j} />
        ))}
      </div>

      {totalPages > 1 && (
        <Pagination
          page={current}
          totalPages={totalPages}
          onChange={(p) => {
            setPage(p);
            window.scrollTo({ top: document.querySelector(".results-heading")?.offsetTop ?? 0, behavior: "smooth" });
          }}
        />
      )}
    </section>
  );
}

function Pagination({ page, totalPages, onChange }) {
  const pages = [];
  for (let p = 1; p <= totalPages; p++) {
    if (p === 1 || p === totalPages || Math.abs(p - page) <= 1) {
      pages.push(p);
    } else if (pages[pages.length - 1] !== "…") {
      pages.push("…");
    }
  }

  return (
    <nav className="pagination" aria-label="Job results pages">
      <button
        type="button"
        className="page-btn"
        disabled={page === 1}
        onClick={() => onChange(page - 1)}
      >
        ← Prev
      </button>
      {pages.map((p, i) =>
        p === "…" ? (
          <span key={`gap-${i}`} className="page-gap">…</span>
        ) : (
          <button
            key={p}
            type="button"
            className={`page-btn ${p === page ? "active" : ""}`}
            onClick={() => onChange(p)}
          >
            {p}
          </button>
        )
      )}
      <button
        type="button"
        className="page-btn"
        disabled={page === totalPages}
        onClick={() => onChange(page + 1)}
      >
        Next →
      </button>
    </nav>
  );
}

function JobCard({ job }) {
  const scoreColor =
    job.score >= 80 ? "score-high" : job.score >= 60 ? "score-mid" : "score-low";
  return (
    <article className="card job">
      <div className="job-head">
        <div>
          <h3>{job.title || "Untitled role"}</h3>
          <div className="muted">
            {job.company || "Unknown company"}
            {job.location ? ` · ${job.location}` : ""}
            {job.is_remote ? " · Remote" : ""}
          </div>
        </div>
        <div className={`score ${scoreColor}`}>
          {job.score}
          <small>match</small>
        </div>
      </div>
      <p className="reason">{job.reason}</p>
      <div className="job-meta">
        {job.salary && <span className="chip">{job.salary}</span>}
        {job.site && <span className="muted">via {job.site}</span>}
        {job.date_posted && <span className="muted">{job.date_posted}</span>}
        {job.url && (
          <a href={job.url} target="_blank" rel="noreferrer">
            View posting →
          </a>
        )}
      </div>
    </article>
  );
}
