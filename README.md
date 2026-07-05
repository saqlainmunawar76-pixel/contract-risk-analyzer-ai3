# ⚖️ AI-Powered Contract & Legal Document Risk Analyzer

**TEYZIX CORE Internship Program — June Batch 2026**
**Task 3 (AI-3) — Advanced AI Application**
**Ref ID:** TC-INT-18991230-763
**Developer:** Saqlain Munawar — IT Student, Emerson University Multan

A production-ready Streamlit application that lets users upload contracts and legal
documents, automatically extracts structured information, detects risky clauses,
generates plain-English summaries, answers questions via RAG, compares contract
versions, and exports professional PDF/DOCX analysis reports — all with secure,
role-based user authentication.

---

## ✨ Features

### Core Features
- 🔐 **Secure Authentication** — bcrypt password hashing, register/login/logout, role-based access (user/admin)
- 📤 **Document Upload** — PDF, DOCX, TXT with size/type validation and OCR fallback for scanned pages
- 🧠 **AI Document Analysis** — contract type, parties, dates, payment terms, renewal, confidentiality, termination, responsibilities
- ⚠️ **Risk Detection** — missing standard clauses, high-risk clause patterns, confidence scores, plain-English explanations
- 📝 **AI Summary** — executive summary, key obligations, important dates, recommended actions
- 🔎 **Semantic Search** — natural-language search within a document (TF-IDF + cosine similarity, no ChromaDB)
- 📊 **AI Insights Dashboard** — usage stats, document-type charts, per-user history
- 📥 **Report Generation** — polished PDF (ReportLab) and DOCX (python-docx) export
- 📁 **Document History** — every user can revisit previously uploaded/analyzed documents
- 🛠️ **Admin Panel** — user management, all-documents view, full audit log

### Bonus Features (all 8 implemented)
1. 💬 **RAG-Based Question Answering** — AI chat assistant grounded in the uploaded document
2. 🌐 **Multi-Language Document Analysis** — auto-detects the contract's language
3. 🔀 **AI Clause Comparison** — upload two contract versions, get matched clause-by-clause differences
4. 🖼️ **OCR for Scanned Documents** — pytesseract fallback when a PDF page has no extractable text
5. ✅ **Compliance Score** — 0–100 score + letter grade with an AI/rule-based explanation
6. 📑 **Version Comparison** — side-by-side clause similarity metrics between two contracts
7. 📧 **Report Delivery** — download-ready PDF/DOCX in place of voice summary (no SMTP dependency required)
8. 🎯 **Explainable Compliance Scoring** — every score comes with a written breakdown of deductions

---

## 🏗️ Architecture

```
task3/
├── app.py                     # Streamlit dashboard — wires all modules together
├── requirements.txt
├── packages.txt                # apt package for Streamlit Cloud (tesseract-ocr)
├── .env.example
├── .streamlit/
│   └── config.toml            # TEYZIX green theme (#1a5d3a)
├── src/
│   ├── storage.py             # SQLite: users, documents, analyses, audit_log
│   ├── auth.py                 # bcrypt auth, validation, role checks
│   ├── document_processor.py  # PDF/DOCX/TXT extraction + OCR fallback
│   ├── ai_analyzer.py          # Gemini-powered analysis + rule-based fallbacks
│   ├── semantic_search.py     # NumPy/sklearn TF-IDF vector search (chromadb-free)
│   └── report_generator.py    # PDF + DOCX report builders
├── data/
│   ├── app.db                  # created automatically on first run
│   └── sample_contracts/       # 4 ready-to-test sample contracts (low/medium/high risk)
├── docs/
│   └── ARCHITECTURE.md         # data flow + design-decision notes
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

# 5. (Optional) add your Gemini API key
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

## ☁️ Deploying to Streamlit Community Cloud

1. Push this project to a GitHub repository (exclude `data/app.db` and `.env` — see `.gitignore`-style advice below).
2. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app pointing at `app.py`.
3. Streamlit Cloud will read `requirements.txt` (Python packages) and `packages.txt`
   (the `tesseract-ocr` system package needed for OCR) automatically.
4. In **App Settings → Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your_key_here"
   ```
5. Deploy. The SQLite database (`data/app.db`) will be created automatically on
   first run — note that Streamlit Cloud's filesystem is ephemeral, so data
   resets on redeploys/restarts. For persistent production use, point
   `storage.DB_PATH` at a mounted volume or swap in a hosted database.

---

## 🧪 Testing Notes

Every module in `src/` was unit-tested independently before integration:
- `storage.py` — CRUD across all 4 tables, dashboard stats
- `auth.py` — registration validation, duplicate detection, password strength, login/logout, first-user-becomes-admin
- `document_processor.py` — TXT, DOCX (with tables), text-based PDF, and **scanned/image-only PDF via OCR**
- `semantic_search.py` — chunking, TF-IDF search, cross-document corpus search, clause comparison
- `ai_analyzer.py` — every AI feature's rule-based fallback path, plus JSON-parsing/markdown-fence-stripping logic for the Gemini response path
- `report_generator.py` — generated PDF/DOCX were reopened and their text verified
- `app.py` — full end-to-end flow (register → login → upload → analyze → search → compare → admin panel) verified with Streamlit's `AppTest` framework, zero exceptions

Three sample contracts of increasing risk are included in `data/sample_contracts/`
so graders can immediately test Low / Medium / High risk detection without
needing their own files.

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
| Local-first, tested with `streamlit.testing.v1.AppTest` before any deployment | Catch integration bugs before pushing to GitHub |

---

## 📄 License / Disclaimer

This tool is built for the TEYZIX CORE Internship Program as an educational/
portfolio project. AI-generated and rule-based analyses **do not constitute
legal advice** — always have contracts reviewed by a qualified lawyer before
signing.
