# Architecture & Data Flow

## High-Level Flow

```
                         ┌─────────────────────┐
                         │   Streamlit UI       │
                         │      (app.py)        │
                         └──────────┬───────────┘
                                    │
        ┌───────────────┬──────────┼──────────┬───────────────┐
        │               │          │          │               │
        ▼               ▼          ▼          ▼               ▼
   ┌─────────┐   ┌──────────────┐ ┌────────┐ ┌────────────┐ ┌──────────────┐
   │ auth.py │   │ document_    │ │ ai_    │ │ semantic_  │ │ report_      │
   │         │   │ processor.py │ │analyzer│ │ search.py  │ │ generator.py │
   └────┬────┘   └──────┬───────┘ │  .py   │ └─────┬──────┘ └──────┬───────┘
        │               │         └───┬────┘       │               │
        │               │             │            │               │
        └───────────────┴─────────────┴────────────┴───────────────┘
                                    │
                                    ▼
                          ┌───────────────────┐
                          │   storage.py       │
                          │  (SQLite: users,   │
                          │  documents,        │
                          │  analyses,         │
                          │  audit_log)        │
                          └───────────────────┘
```

## Request Lifecycle: "Upload → Analyze → Export"

1. **Upload** (`app.py` → `document_processor.py`)
   - File is validated (type, size, non-empty).
   - PDF: `pdfplumber` extracts text page-by-page. Any page with no
     extractable text is assumed scanned and rasterized + OCR'd via
     `pytesseract`. If `pdfplumber` itself fails to open the file, `pypdf`
     is tried as a second engine.
   - DOCX: `python-docx` extracts paragraphs + table cell text.
   - TXT: decoded with a fallback chain of encodings.
   - Extracted text + metadata is persisted via `storage.save_document()`.

2. **Analyze** (`app.py` → `ai_analyzer.py` → `semantic_search.py`)
   - `extract_contract_info()`, `detect_risks()`, `generate_summary()`,
     `compliance_score()` are each called with the shared Gemini client
     (or `None` if no API key).
   - Each function tries the Gemini path first (JSON-only prompt →
     `_call_gemini_json()`, which strips markdown fences and parses JSON).
     Any exception (network, quota, malformed JSON) triggers an immediate
     fallback to the deterministic rule-based path — the user never sees
     an error, just a `source: "fallback"` tag in the result.
   - Risk detection's rule-based path checks for 10 standard clause types
     (missing = medium risk) and 6 high-risk regex patterns (unlimited
     liability, one-sided auto-renewal, unilateral termination, broad
     indemnification, no liability cap, jury-trial waiver).
   - Compliance scoring (fallback) starts at 100 and deducts 15 points per
     high-risk finding and 8 points per missing standard clause.
   - Results are cached in `st.session_state` and persisted via
     `storage.save_analysis()` so re-visiting a document doesn't require
     re-running the (potentially paid) AI call.

3. **Search & Chat** (`semantic_search.py`)
   - The document is chunked (≈800 chars, 150 overlap, sentence-boundary
     aware) and indexed with a `TfidfVectorizer` at load time.
   - Semantic Search: query is vectorized and compared via cosine
     similarity against all chunks; top-k returned with scores.
   - RAG Q&A: same retrieval, but the top-3 chunks are joined into a
     context block and passed to Gemini with an instruction to answer
     only from that context. Fallback: the most relevant chunk is
     returned directly as an "extractive answer".

4. **Compare** (`semantic_search.compare_clauses` → `ai_analyzer.compare_contracts`)
   - Both documents are chunked (smaller: 500 chars) and every chunk in A
     is matched to its most similar chunk in B via cosine similarity.
   - Gemini (if available) explains the practical difference between each
     matched pair in one sentence; fallback reports the raw similarity
     score.

5. **Export** (`report_generator.py`)
   - Takes the four analysis dicts (info, risks, summary, compliance) and
     renders a styled PDF (ReportLab `SimpleDocTemplate` + `Table`) and a
     DOCX (`python-docx` headings/tables/bullets), both in the TEYZIX
     green color scheme, returned as in-memory bytes for
     `st.download_button` (no temp files touch disk).

## Why No ChromaDB?

Streamlit Community Cloud's build image failed to resolve ChromaDB's
transitive dependencies against Python 3.14, breaking deployments outright.
Since the actual requirement is "search within one document" / "search a
handful of a user's documents" (not billion-scale vector search), a
TF-IDF + cosine-similarity index built fresh per document with
`scikit-learn` + `numpy` is more than sufficient, has zero native build
dependencies, and deploys reliably everywhere.

## Why Every AI Feature Has a Rule-Based Fallback

1. **Reliability** — the app must work in local dev without any API key.
2. **Cost control** — reviewers/graders can exercise every feature without
   consuming API quota.
3. **Resilience** — a transient Gemini outage or malformed JSON response
   degrades gracefully to a slightly-less-smart but still useful result,
   instead of a crash or blank screen.

## Security Notes

- Passwords are hashed with bcrypt (cost factor 12); plaintext is never
  stored, logged, or included in the audit log.
- Login and "unknown user" failures return an identical error message to
  avoid username enumeration.
- Role checks (`auth.is_admin()`) gate the Admin tab and its underlying
  `storage` queries (user list, all documents, audit log).
- File uploads are size- and extension-validated before any parsing library
  ever touches the bytes.
