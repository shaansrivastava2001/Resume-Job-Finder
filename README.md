# Resume-Based Job Finder

Upload a resume + preferences. A local Ollama LLM extracts your profile, then live job postings (Indeed / LinkedIn / ZipRecruiter / Google) are scraped via [JobSpy](https://github.com/Bunsly/JobSpy) and ranked by the same LLM.

```
resume.pdf ──▶ Ollama (extract profile) ──▶ JobSpy (scrape) ──▶ Ollama (rank) ──▶ React UI
```

## Stack
- **Backend:** Python · FastAPI · pypdf · python-docx · ollama · python-jobspy
- **Frontend:** React 18 · Vite
- **LLM:** local Ollama (`mistral:latest` by default; configurable via `OLLAMA_MODEL`)

## Prerequisites
- Python 3.10+
- Node 18+
- [Ollama](https://ollama.com) running locally with `mistral` available
  ```bash
  ollama list             # confirm mistral:latest is installed
  ollama serve            # usually already running
  ```

## Backend setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit if you want a different model

# load env and run
set -a; source .env; set +a
uvicorn main:app --reload --port 8000
```

Health check: <http://localhost:8000/api/health>

## Frontend setup
```bash
cd frontend
npm install
npm run dev
```
Open <http://localhost:5173>. Vite proxies `/api/*` to the backend on port 8000.

## How it works
1. `POST /api/search` accepts a multipart form: resume file + salary, location, country, remote, free-text preferences.
2. `resume_parser.py` extracts text from PDF / DOCX / TXT.
3. `llm.extract_profile` asks Ollama (JSON mode) for `{current_title, seniority, years_experience, top_skills, preferred_roles, summary}`.
4. `jobs.search_jobs` runs JobSpy for each preferred role across Indeed, LinkedIn, ZipRecruiter, Google, dedupes by URL.
5. `llm.rank_jobs` sends the profile + preferences + compacted job descriptions back to Ollama, gets a 0-100 score and one-line reason per job.
6. UI renders the ranked list with a colored score badge.

## Notes / gotchas
- **Scraping is fragile.** Indeed and LinkedIn actively block scrapers. JobSpy handles request shaping but expect occasional empty results, especially without a residential IP. If a site stops working, JobSpy logs the error and we continue with the others.
- **Rate limits.** Don't hammer the endpoint. Each search runs up to 4 search terms × 4 sites.
- **Model choice.** `mistral:latest` (7B, ~4.4GB) is the default. Swap via `OLLAMA_MODEL` env var — e.g. `llama3.2:latest` for faster but lower-quality ranking, or a larger model if you have one pulled.
- **Ranking time.** Sending ~60 job descriptions through a 7B model can take 20–60s. Reduce `results_per_term` in `backend/jobs.py` if it's too slow.
- **ToS.** Scraping LinkedIn violates their ToS. Personal/educational use only.

## Project layout
```
backend/
  main.py           FastAPI app + /api/search
  resume_parser.py  PDF / DOCX / TXT extraction
  llm.py            Ollama profile extraction + ranking
  jobs.py           JobSpy wrapper + normalization
  requirements.txt
  .env.example
frontend/
  src/
    App.jsx         Form + results
    main.jsx
    styles.css
  vite.config.js    Proxies /api → :8000
  package.json
```
