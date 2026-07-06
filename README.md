# ⚖️ AI-Powered Contract & Legal Document Risk Analyzer

**TEYZIX CORE Internship Program — June Batch 2026**
**Task ID: AI-3 — AI-Powered Contract & Legal Document Risk Analyzer**
**Ref ID:** TC-INT-18991230-763
**Developer:** Saqlain Munawar — IT Student, Emerson University Multan

A production-ready Streamlit application that lets users upload contracts and legal
documents, automatically extracts structured information, detects risky clauses,
generates plain-English summaries, answers questions via RAG, compares contract
versions, and exports professional PDF/DOCX analysis reports — all with secure,
role-based user authentication and a modern black & blue interface.

---

## ✅ Requirement Coverage (against the official Task AI-3 brief)

### Core Features — all 10 implemented

| # | Requirement | Where |
|---|---|---|
| 1 | Secure User Authentication (Registration, Login, Role-Based Access, **Profile Management**) | `src/auth.py`, Profile tab in `app.py` |
| 2 | Document Upload (PDF/DOCX/TXT + validation) | `src/document_processor.py` |
| 3 | AI Document Analysis (type, parties, dates, payment, renewal, confidentiality, termination, responsibilities) | `src/ai_analyzer.py::extract_contract_info` |
| 4 | Risk Detection (missing clauses, high-risk conditions, **ambiguous statements**, **unusual payment terms**, confidence + explanation) | `src/ai_analyzer.py::detect_risks` |
| 5 | AI Summary (executive summary, obligations, dates, **important clauses**, recommended actions) | `src/ai_analyzer.py::generate_summary` |
| 6 | Semantic Search (natural-language queries) | `src/semantic_search.py`, Search & Chat tab |
| 7 | AI Insights Dashboard (total docs, **avg. risk score**, **high-risk doc count**, **frequently detected risks**, processing history) | `storage.get_user_risk_insights`, Insights tab |
| 8 | Report Generation (PDF + DOCX: risk assessment, summary, clause analysis, recommendations) | `src/report_generator.py` |
| 9 | Document History (uploaded docs, previous analyses, processing date, AI results, risk reports) | dedicated History tab |
| 10 | Admin Panel (manage users, **processing statistics**, **AI usage monitoring**, manage documents, system logs) | Admin tab |

### Bonus Features — all 9 implemented

| # | Bonus Feature | Where |
|---|---|---|
| 1 | RAG-Based Question Answering | `ai_analyzer.answer_question` (AI Chat) |
| 2 | Multi-Language Document Analysis | `ai_analyzer.detect_language` |
| 3 | AI Clause Comparison | `ai_analyzer.compare_contracts` + Compare tab |
| 4 | OCR for Scanned Documents | `document_processor.py` (pytesseract fallback) |
| 5 | Voice Summary Generation → **Email Report Delivery** (substituted, as pre-approved) | `src/notifier.py`, SMTP-based |
| 6 | Email Report Delivery | `src/notifier.py` (graceful no-op if SMTP unset) |
| 7 | AI Compliance Score | `ai_analyzer.compliance_score` |
| 8 | Version Comparison Between Contracts | Compare tab (clause-level similarity) |
| 9 | **Docker Deployment** | `Dockerfile`, `docker-compose.yml` |

---

## ✨ Feature Highlights

- 🔐 **Secure Authentication** — bcrypt password hashing, register/login/logout, role-based access, full profile management (change email/password)
- 📤 **Document Upload** — PDF, DOCX, TXT with size/type validation and OCR fallback for scanned pages
- 🧠 **AI Document Analysis** — contract type, parties, dates, payment terms, renewal, confidentiality, termination, responsibilities
- ⚠️ **Risk Detection** — 4 risk categories (high-risk clauses, missing clauses, ambiguous statements, unusual payment terms), each with a confidence score and plain-English explanation
- 📝 **AI Summary** — executive summary, key obligations, important dates, important clauses, recommended actions
- 🔎 **Semantic Search** — natural-language search within a document (TF-IDF + cosine similarity, no ChromaDB)
- 📊 **AI Insights Dashboard** — average compliance score, high-risk document count, most frequently detected risk types, full processing history
- 📥 **Report Generation** — polished PDF (ReportLab) and DOCX (python-docx) export, plus optional email delivery
- 📁 **Document History** — per-document expandable history of every previous analysis
- 🛠️ **Admin Panel** — user management, processing statistics, AI-vs-fallback usage monitoring, all-documents view, full audit log
- 🐳 **Docker Deployment** — one-command containerized deployment via `docker-compose up`
- 🎨 **Professional Black & Blue UI** — modern dark theme with gradient hero banners, glassy cards, and risk-level badges

---

## 🏗️ Architecture

```
task3/
├── app.py                     # Streamlit dashboard — wires all modules together
├── requirements.txt
├── packages.txt                # apt package for Streamlit Cloud (tesseract-ocr)
├── Dockerfile                  # Docker deployment (bonus feature)
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── .streamlit/
│   └── config.toml            # Black & Blue dark theme
├── src/
│   ├── storage.py             # SQLite: users, documents, analyses, audit_log + dashboard aggregation
│   ├── auth.py                 # bcrypt auth, validation, role checks, profile management
│   ├── document_processor.py  # PDF/DOCX/TXT extraction + OCR fallback
│   ├── ai_analyzer.py          # Gemini-powered analysis + rule-based fallbacks
│   ├── semantic_search.py     # NumPy/sklearn TF-IDF vector search (chromadb-free)
│   ├── report_generator.py    # PDF + DOCX report builders
│   └── notifier.py             # Optional SMTP email report delivery
├── data/
│   ├── app.db                  # created automatically on first run
│   └── sample_contracts/       # 4 ready-to-test sample contracts (low/medium/high risk)
├── docs/
│   └── ARCHITECTURE.md         # data flow diagram + design-decision notes
└── screenshots/                # add your own app screenshots here for submission
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a full data-flow diagram and
the reasoning behind each technical decision.

---

## 🚀 Quick Start (Local)

```bash
# 1. Clone / unzip the project, then enter the folder
cd task3

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install the Tesseract OCR binary (only needed for scanned-PDF OCR)
#    Ubuntu/Debian: sudo apt-get install tesseract-ocr
#    macOS:         brew install tesseract
#    Windows:       https://github.com/UB-Mannheim/tesseract/wiki

# 5. (Optional) add your Gemini API key + SMTP settings for email delivery
cp .env.example .env
# edit .env and set GEMINI_API_KEY=your_key
# Get a free key at https://aistudio.google.com/apikey

# 6. Run the app
streamlit run app.py
```

The app works **fully without a Gemini API key** — every AI feature (info
extraction, risk detection, summarization, RAG Q&A, clause comparison,
compliance scoring, language detection) has a deterministic rule-based
fallback, so you can develop and demo offline.

The first account you register on a fresh database is automatically made an
**admin**, so there's always at least one admin without manual DB edits.

---

## 🐳 Run with Docker

```bash
# Build and run (SQLite data persists in ./data via a mounted volume)
docker compose up --build

# Or without compose:
docker build -t contract-risk-analyzer .
docker run -p 8501:8501 -e GEMINI_API_KEY=your_key -v $(pwd)/data:/app/data contract-risk-analyzer
```

Open http://localhost:8501

---

## ☁️ Deploying to Streamlit Community Cloud

1. Push this project to a GitHub repository (exclude `data/app.db` and `.env`).
2. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app pointing at `app.py`.
3. Streamlit Cloud will read `requirements.txt` (Python packages) and `packages.txt`
   (the `tesseract-ocr` system package needed for OCR) automatically.
4. In **App Settings → Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your_key_here"
   # Optional, for Email Report Delivery:
   SMTP_HOST = "smtp.gmail.com"
   SMTP_PORT = "587"
   SMTP_USERNAME = "your_email@gmail.com"
   SMTP_PASSWORD = "your_app_password"
   SMTP_FROM_EMAIL = "your_email@gmail.com"
   ```
5. Deploy. The SQLite database (`data/app.db`) will be created automatically on
   first run — note that Streamlit Cloud's filesystem is ephemeral, so data
   resets on redeploys/restarts. For persistent production use, point
   `storage.DB_PATH` at a mounted volume or swap in a hosted database.

---

## 🧪 Testing Notes

Every module in `src/` was unit-tested independently before integration:
- `storage.py` — CRUD across all 4 tables, dashboard stats, risk insight aggregation, AI usage stats
- `auth.py` — registration validation, duplicate detection, password strength, login/logout, first-user-becomes-admin, password change, email update
- `document_processor.py` — TXT, DOCX (with tables), text-based PDF, and **scanned/image-only PDF via OCR**
- `semantic_search.py` — chunking, TF-IDF search, cross-document corpus search, clause comparison
- `ai_analyzer.py` — every AI feature's rule-based fallback path (including the 4 risk categories), plus JSON-parsing/markdown-fence-stripping logic for the Gemini response path
- `report_generator.py` — generated PDF/DOCX were reopened and their text verified
- `notifier.py` — graceful handling of unconfigured and misconfigured SMTP without raising
- `app.py` — full end-to-end flow (register → login → upload → analyze → search → compare → history → insights → profile → admin) verified with Streamlit's `AppTest` framework, zero exceptions

Three sample contracts of increasing risk are included in `data/sample_contracts/`
so graders can immediately test Low / Medium / High risk detection without
needing their own files.

**Bugs found and fixed during testing** (documented for transparency):
- Regex risk patterns weren't matching across newlines (`.` vs `[\s\S]`), causing
  some high-risk clauses to be silently missed.
- A short keyword ("nda") was matching as a substring inside unrelated words
  (e.g. "recomme**nda**tions"), causing false clause detections — fixed with
  proper word-boundary regex.
- `use_container_width` (deprecated Streamlit parameter) replaced with `width='stretch'`.

---

## 🔑 Critical Technical Decisions

| Decision | Reasoning |
|---|---|
| `google-genai` SDK (not `google-generativeai`) | The old SDK was deprecated Nov 2025 |
| `ThinkingConfig(thinking_budget=0)` | Prevents Gemini 2.5's thinking mode from truncating responses |
| Model: `gemini-2.5-flash` | `gemini-2.0-flash` was shut down June 2026 |
| NumPy + scikit-learn TF-IDF (no ChromaDB) | ChromaDB breaks on Streamlit Cloud (Python 3.14 dependency conflict) |
| SQLite | No server needed, works everywhere, ships as a single file |
| Every AI feature has a rule-based fallback | App stays fully usable with zero API key / quota |
| Email delivery is fully optional (`notifier.py`) | App must not error out when SMTP isn't configured |
| Local-first, tested with `streamlit.testing.v1.AppTest` before any deployment | Catch integration bugs before pushing to GitHub |

---

## 📄 License / Disclaimer

This tool is built for the TEYZIX CORE Internship Program as an educational/
portfolio project. AI-generated and rule-based analyses **do not constitute
legal advice** — always have contracts reviewed by a qualified lawyer before
signing.
