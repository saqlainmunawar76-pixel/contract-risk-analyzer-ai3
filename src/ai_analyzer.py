"""
ai_analyzer.py
==============
All AI-powered contract analysis lives here: info extraction, risk detection,
summarization, RAG Q&A, clause comparison, compliance scoring, and language
detection.

CRITICAL DECISIONS THIS MODULE FOLLOWS (per project spec):
    - Uses the NEW `google-genai` SDK (`from google import genai`), never the
      deprecated `google-generativeai`.
    - Model: "gemini-2.5-flash".
    - ThinkingConfig(thinking_budget=0) is set on every call so Gemini 2.5's
      "thinking" mode doesn't eat the token budget and truncate answers.
    - GRACEFUL FALLBACK: every single AI feature below has a deterministic,
      rule-based fallback path so the app remains fully usable even with no
      GEMINI_API_KEY configured (e.g. during local dev, or if the key quota
      runs out). The fallback is not a stub -- it does real, useful analysis
      with regex/keyword/TF-IDF heuristics.

Every public function returns a plain dict with a "source" key set to
either "ai" or "fallback" so the UI (app.py) can show the user which mode
produced the result.
"""

import json
import re
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from src.semantic_search import SemanticIndex, chunk_text, compare_clauses as _compare_clauses_vectors

MODEL_NAME = "gemini-2.5-flash"

# ---- Common clauses we check for in risk detection & compliance scoring ----
STANDARD_CLAUSES = {
    "termination": ["terminat", "end this agreement", "cancel this agreement"],
    "confidentiality": ["confidential", "non-disclosure"],
    "indemnification": ["indemnif", "hold harmless"],
    "governing_law": ["governing law", "jurisdiction", "applicable law"],
    "liability": ["liability", "limitation of liability", "liable for damages"],
    "dispute_resolution": ["dispute", "arbitration", "mediation", "litigation"],
    "payment_terms": ["payment", "invoice", "fee", "compensation"],
    "renewal": ["renew", "extension of term", "automatic renewal"],
    "force_majeure": ["force majeure", "act of god"],
    "intellectual_property": ["intellectual property", "copyright", "trademark", "patent"],
}

HIGH_RISK_PATTERNS = {
    "unlimited_liability": r"unlimited liability|no limit(?:ation)? on liability",
    "auto_renewal_no_notice": r"automatically renew[\s\S]{0,80}without (?:notice|prior notice)",
    "unilateral_termination": (
        r"(?:sole|absolute) discretion[\s\S]{0,60}terminat|terminat[\s\S]{0,60}(?:sole|absolute) discretion"
    ),
    "broad_indemnification": r"indemnif(?:y|ication)[\s\S]{0,120}(?:any and all|all claims|regardless of)",
    "no_liability_cap": r"no cap on|without limitation[\s\S]{0,40}damages|no cap on damages",
    "exclusive_jurisdiction_waiver": r"waiv(?:e|es|ing)[\s\S]{0,60}(?:right to|jury trial|appeal)",
}

AMBIGUOUS_STATEMENT_PATTERNS = {
    "vague_effort_standard": r"reasonable (?:efforts|endeavors)|best efforts|commercially reasonable",
    "vague_timing": r"from time to time|as (?:needed|required|necessary)(?! by law)",
    "unilateral_discretion_clause": r"in its (?:sole |absolute )?discretion|as (?:it|the company) (?:deems|sees) fit",
    "undefined_standard": r"material(?:ly)? (?:breach|change|adverse)|substantial(?:ly)? (?:compliance|complete)",
}

UNUSUAL_PAYMENT_PATTERNS = {
    "full_upfront_nonrefundable": r"(?:100\s?%|full amount)[\s\S]{0,40}(?:non-refundable|advance|upfront)",
    "payment_on_demand": r"payable (?:immediately|on demand|upon demand)",
    "uncapped_late_fee": r"(?:penalty|interest)[\s\S]{0,50}maximum rate permitted",
    "penalty_no_grace_period": r"(?:late fee|penalty)[\s\S]{0,40}(?:immediately|no grace period)",
}


# --------------------------------------------------------------- client ----
def get_client(api_key: str):
    """Return a google-genai Client, or None if no key is configured."""
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _call_gemini_json(client, prompt: str) -> dict:
    """
    Call Gemini with thinking disabled, expecting a JSON-only response.
    Strips markdown fences defensively and raises on any failure so the
    caller can fall back to the rule-based path.
    """
    from google.genai import types

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            temperature=0.2,
        ),
    )
    text = (response.text or "").strip()
    text = re.sub(r"^```json\s*|^```\s*|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def _call_gemini_text(client, prompt: str) -> str:
    from google.genai import types

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            temperature=0.3,
        ),
    )
    return (response.text or "").strip()


# ------------------------------------------------------- info extraction ----
def extract_contract_info(text: str, client=None) -> dict:
    if client:
        try:
            prompt = f"""You are a legal document analyst. Extract structured information from this
contract as JSON only (no markdown, no commentary). Use this exact schema:
{{
  "contract_type": "string",
  "parties": ["string", ...],
  "effective_date": "string or null",
  "expiration_date": "string or null",
  "payment_terms": "string or null",
  "renewal_terms": "string or null",
  "confidentiality_clause": "string or null (brief description)",
  "termination_clause": "string or null (brief description)",
  "key_responsibilities": ["string", ...]
}}

Contract text:
{text[:12000]}
"""
            result = _call_gemini_json(client, prompt)
            result["source"] = "ai"
            return result
        except Exception:
            pass  # fall through to rule-based extraction

    return _extract_contract_info_fallback(text)


def _extract_contract_info_fallback(text: str) -> dict:
    dates = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b",
        text, flags=re.IGNORECASE,
    )
    # Parties: look for capitalized multi-word sequences near "between"/"and", crude but useful
    parties = []
    between_match = re.search(
        r"between\s+(.+?)\s+and\s+(.+?)(?:,|\.|\bon\b|\bdated\b|\bwhereby\b|\n)", text, flags=re.IGNORECASE
    )
    if between_match:
        parties = [between_match.group(1).strip(), between_match.group(2).strip()]
    else:
        caps = re.findall(r"\b([A-Z][a-zA-Z&,.]+(?: [A-Z][a-zA-Z&,.]+){0,3}(?: Inc\.?| LLC| Ltd\.?| Corp\.?)?)\b", text)
        parties = list(dict.fromkeys([c for c in caps if len(c) > 3]))[:2]

    payment_match = re.search(r"([^.]*\b(?:payment|invoice|fee)s?\b[^.]*\.)", text, flags=re.IGNORECASE)
    renewal_match = re.search(r"([^.]*\brenew\w*\b[^.]*\.)", text, flags=re.IGNORECASE)
    confidentiality_match = re.search(r"([^.]*\bconfidential\w*\b[^.]*\.)", text, flags=re.IGNORECASE)
    termination_match = re.search(r"([^.]*\bterminat\w*\b[^.]*\.)", text, flags=re.IGNORECASE)

    contract_type = "General Agreement"
    type_keywords = {
        "Employment Agreement": ["employee", "employment", "salary", "job title"],
        "Non-Disclosure Agreement": ["non-disclosure", "nda", "confidential information"],
        "Service Agreement": ["services", "service provider", "scope of work"],
        "Lease Agreement": ["lease", "tenant", "landlord", "rent"],
        "License Agreement": ["license", "licensor", "licensee"],
        "Sales Agreement": ["purchase", "buyer", "seller", "goods"],
    }
    text_lower = text.lower()
    for label, keywords in type_keywords.items():
        if any(re.search(r"\b" + re.escape(kw) + r"\b", text_lower) for kw in keywords):
            contract_type = label
            break

    responsibilities = re.findall(r"([^.]*\b(?:shall|must|agrees to|is responsible for)\b[^.]*\.)", text, flags=re.IGNORECASE)

    return {
        "contract_type": contract_type,
        "parties": parties if parties else ["Not clearly identified"],
        "effective_date": dates[0] if dates else None,
        "expiration_date": dates[1] if len(dates) > 1 else None,
        "payment_terms": payment_match.group(1).strip() if payment_match else None,
        "renewal_terms": renewal_match.group(1).strip() if renewal_match else None,
        "confidentiality_clause": confidentiality_match.group(1).strip() if confidentiality_match else None,
        "termination_clause": termination_match.group(1).strip() if termination_match else None,
        "key_responsibilities": [r.strip() for r in responsibilities[:5]],
        "source": "fallback",
    }


# --------------------------------------------------------- risk detection --
def detect_risks(text: str, client=None) -> dict:
    rule_based = _detect_risks_fallback(text)

    if client:
        try:
            prompt = f"""You are a contract risk analyst. Review this contract and return JSON only:
{{
  "risks": [
    {{"clause": "string", "risk_level": "high|medium|low", "explanation": "string",
      "confidence": 0.0-1.0, "risk_category": "high_risk_clause|missing_clause|ambiguous_statement|unusual_payment_term"}}
  ],
  "missing_clauses": ["string", ...],
  "overall_risk_level": "high|medium|low"
}}
Check for ALL of these categories:
1. High-risk clauses: unlimited liability, one-sided termination rights, broad indemnification,
   unfavorable auto-renewal, waived jury trial/appeal rights.
2. Missing standard clauses: dispute resolution, confidentiality, governing law, liability caps, etc.
3. Ambiguous statements: vague standards like "reasonable efforts", "as needed", clauses left to one
   party's sole discretion, undefined terms like "material breach" without a definition.
4. Unusual payment terms: 100% non-refundable upfront payment, payment due immediately/on demand,
   uncapped or maximum-rate-permitted late fees/penalties, missing payment schedule.

IMPORTANT: every single item in "risks" MUST include a numeric "confidence" value between 0.0 and 1.0
(your certainty that this is a real issue). Never omit it and never set it to 0 unless you are
genuinely uncertain the issue exists at all.

Contract text:
{text[:12000]}
"""
            result = _call_gemini_json(client, prompt)
            result["source"] = "ai"
            return _sanitize_risks_result(result)
        except Exception:
            pass

    return rule_based


def _sanitize_risks_result(result: dict) -> dict:
    """
    Defensively fill in any fields the LLM omitted or returned as null/out-of-range,
    so the UI never shows a misleading '0% confidence' or crashes on a missing key.
    """
    default_confidence_by_level = {"high": 0.8, "medium": 0.65, "low": 0.5}

    cleaned_risks = []
    for risk in result.get("risks", []) or []:
        level = risk.get("risk_level") or "medium"
        if level not in ("high", "medium", "low"):
            level = "medium"

        confidence = risk.get("confidence")
        if not isinstance(confidence, (int, float)) or confidence <= 0:
            confidence = default_confidence_by_level[level]
        confidence = max(0.0, min(1.0, float(confidence)))

        cleaned_risks.append({
            "clause": risk.get("clause") or "Unnamed clause",
            "risk_level": level,
            "explanation": risk.get("explanation") or "No further explanation provided.",
            "confidence": confidence,
            "risk_category": risk.get("risk_category") or "high_risk_clause",
        })

    result["risks"] = cleaned_risks
    result.setdefault("missing_clauses", [])
    if result.get("overall_risk_level") not in ("high", "medium", "low"):
        high_count = sum(1 for r in cleaned_risks if r["risk_level"] == "high")
        result["overall_risk_level"] = "high" if high_count >= 2 else ("medium" if high_count == 1 else "low")
    return result


def _detect_risks_fallback(text: str) -> dict:
    text_lower = text.lower()
    risks = []
    missing_clauses = []

    for clause_name, keywords in STANDARD_CLAUSES.items():
        found = any(re.search(r"\b" + re.escape(kw) + r"\w*", text_lower) for kw in keywords)
        if not found:
            missing_clauses.append(clause_name.replace("_", " ").title())

    for risk_name, pattern in HIGH_RISK_PATTERNS.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            snippet_start = max(0, match.start() - 60)
            snippet_end = min(len(text), match.end() + 60)
            risks.append({
                "clause": risk_name.replace("_", " ").title(),
                "risk_level": "high",
                "explanation": f"Pattern matched: \u2018...{text[snippet_start:snippet_end].strip()}...\u2019",
                "confidence": 0.7,
                "risk_category": "high_risk_clause",
            })

    for risk_name, pattern in AMBIGUOUS_STATEMENT_PATTERNS.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            snippet_start = max(0, match.start() - 50)
            snippet_end = min(len(text), match.end() + 50)
            risks.append({
                "clause": f"Ambiguous: {risk_name.replace('_', ' ').title()}",
                "risk_level": "medium",
                "explanation": f"Vague/undefined language found: \u2018...{text[snippet_start:snippet_end].strip()}...\u2019. Consider defining this term precisely.",
                "confidence": 0.55,
                "risk_category": "ambiguous_statement",
            })

    for risk_name, pattern in UNUSUAL_PAYMENT_PATTERNS.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            snippet_start = max(0, match.start() - 50)
            snippet_end = min(len(text), match.end() + 50)
            risks.append({
                "clause": f"Unusual Payment Term: {risk_name.replace('_', ' ').title()}",
                "risk_level": "high",
                "explanation": f"Non-standard payment condition detected: \u2018...{text[snippet_start:snippet_end].strip()}...\u2019",
                "confidence": 0.65,
                "risk_category": "unusual_payment_term",
            })

    for clause in missing_clauses:
        risks.append({
            "clause": f"Missing: {clause}",
            "risk_level": "medium",
            "explanation": f"No '{clause}' language was detected. This clause is standard in most contracts and its absence may leave a party unprotected.",
            "confidence": 0.6,
            "risk_category": "missing_clause",
        })

    high_count = sum(1 for r in risks if r["risk_level"] == "high")
    if high_count >= 2:
        overall = "high"
    elif high_count == 1 or len(missing_clauses) >= 3:
        overall = "medium"
    else:
        overall = "low"

    return {
        "risks": risks,
        "missing_clauses": missing_clauses,
        "overall_risk_level": overall,
        "source": "fallback",
    }


# --------------------------------------------------------------- summary ---
def generate_summary(text: str, client=None) -> dict:
    if client:
        try:
            prompt = f"""Summarize this contract for a busy executive. Return JSON only:
{{
  "executive_summary": "2-4 sentence plain-English summary",
  "key_obligations": ["string", ...],
  "important_dates": ["string", ...],
  "important_clauses": ["string - name and 1-line description of each notable clause", ...],
  "recommended_actions": ["string", ...]
}}

Contract text:
{text[:12000]}
"""
            result = _call_gemini_json(client, prompt)
            result["source"] = "ai"
            return result
        except Exception:
            pass

    return _generate_summary_fallback(text)


def _generate_summary_fallback(text: str) -> dict:
    """Extractive summary via TF-IDF sentence scoring (same core technique as Task 1)."""
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    sentences = [s for s in sentences if len(s.split()) > 4]
    if not sentences:
        return {
            "executive_summary": "Document too short to summarize.",
            "key_obligations": [],
            "important_dates": [],
            "recommended_actions": ["Review the document manually."],
            "source": "fallback",
        }

    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(sentences)
    scores = np.asarray(matrix.sum(axis=1)).flatten()
    top_n = min(3, len(sentences))
    top_indices = sorted(np.argsort(scores)[::-1][:top_n])
    executive_summary = " ".join(sentences[i] for i in top_indices)

    obligations = re.findall(r"([^.]*\b(?:shall|must|is required to|agrees to)\b[^.]*\.)", text, flags=re.IGNORECASE)
    dates = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4})\b",
        text, flags=re.IGNORECASE,
    )

    actions = []
    if "terminat" not in text.lower():
        actions.append("Add a clear termination clause.")
    if "confidential" not in text.lower():
        actions.append("Consider adding a confidentiality clause.")
    if not dates:
        actions.append("Clarify effective and expiration dates.")
    if not actions:
        actions.append("Have this contract reviewed by legal counsel before signing.")

    important_clauses = []
    for clause_name, keywords in STANDARD_CLAUSES.items():
        for kw in keywords:
            match = re.search(r"\b" + re.escape(kw) + r"\w*", text, flags=re.IGNORECASE)
            if match:
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 80)
                snippet = re.sub(r"\s+", " ", text[start:end]).strip()
                important_clauses.append(f"{clause_name.replace('_', ' ').title()}: \u2026{snippet}\u2026")
                break

    return {
        "executive_summary": executive_summary,
        "key_obligations": [o.strip() for o in obligations[:5]],
        "important_dates": list(dict.fromkeys(dates))[:5],
        "important_clauses": important_clauses[:8],
        "recommended_actions": actions,
        "source": "fallback",
    }


# -------------------------------------------------------------- RAG Q&A ----
def answer_question(text: str, question: str, client=None, semantic_index: SemanticIndex = None) -> dict:
    if semantic_index is None:
        semantic_index = SemanticIndex(text)
    context = semantic_index.get_context_for_rag(question, top_k=3)

    if not context:
        return {
            "answer": "I couldn't find relevant content in this document to answer that question.",
            "context_used": "",
            "source": "fallback",
        }

    if client:
        try:
            prompt = f"""Answer the question using ONLY the contract excerpts below. If the answer isn't
in the excerpts, say so clearly. Be concise (2-4 sentences).

Excerpts:
{context}

Question: {question}
"""
            answer = _call_gemini_text(client, prompt)
            return {"answer": answer, "context_used": context, "source": "ai"}
        except Exception:
            pass

    # Fallback: extractive answer -- just return the most relevant excerpt directly.
    return {
        "answer": f"(Extractive match, no AI available) Most relevant excerpt:\n\n{context[:500]}",
        "context_used": context,
        "source": "fallback",
    }


# ------------------------------------------------------ clause comparison --
def compare_contracts(text_a: str, text_b: str, client=None) -> dict:
    vector_comparisons = _compare_clauses_vectors(text_a, text_b, top_k=5)

    if client:
        try:
            pairs_text = "\n\n".join(
                f"Clause A: {c['clause_a']}\nClause B: {c['clause_b']}" for c in vector_comparisons
            )
            prompt = f"""Compare these matched clause pairs from two contract versions. For each pair,
explain the practical difference in 1 sentence. Return JSON only:
{{"comparisons": [{{"clause_a": "...", "clause_b": "...", "difference": "..."}}]}}

{pairs_text}
"""
            result = _call_gemini_json(client, prompt)
            result["source"] = "ai"
            return result
        except Exception:
            pass

    return {
        "comparisons": [
            {
                "clause_a": c["clause_a"],
                "clause_b": c["clause_b"],
                "difference": f"Similarity score: {c['similarity']:.2f} (no AI explanation available; review manually).",
            }
            for c in vector_comparisons
        ],
        "source": "fallback",
    }


# ------------------------------------------------------- compliance score --
def compliance_score(text: str, risk_result: dict = None, client=None) -> dict:
    if risk_result is None:
        risk_result = detect_risks(text, client=client)

    if client:
        try:
            prompt = f"""Rate this contract's compliance/completeness from 0-100 based on standard
contract best practices (clarity, standard clauses present, balanced risk allocation).
Return JSON only: {{"score": 0-100, "explanation": "string", "grade": "A|B|C|D|F"}}

Contract text:
{text[:10000]}
"""
            result = _call_gemini_json(client, prompt)
            result["source"] = "ai"
            return result
        except Exception:
            pass

    return _compliance_score_fallback(risk_result)


def _compliance_score_fallback(risk_result: dict) -> dict:
    score = 100
    high_risks = sum(1 for r in risk_result.get("risks", []) if r.get("risk_level") == "high")
    missing = len(risk_result.get("missing_clauses", []))
    score -= high_risks * 15
    score -= missing * 8
    score = max(0, min(100, score))

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    explanation = (
        f"Score deducted for {high_risks} high-risk pattern(s) and {missing} missing standard clause(s). "
        f"Grade '{grade}' reflects overall contract completeness against common best-practice checklist items."
    )
    return {"score": score, "explanation": explanation, "grade": grade, "source": "fallback"}


# ------------------------------------------------------ language detection-
COMMON_WORDS_BY_LANG = {
    "English": {"the", "and", "shall", "agreement", "party", "between"},
    "Urdu": {"اور", "کے", "میں", "کا", "ہے", "معاہدہ"},
    "Spanish": {"el", "la", "contrato", "entre", "las", "acuerdo"},
    "French": {"le", "la", "contrat", "entre", "accord", "les"},
    "Arabic": {"في", "من", "على", "العقد", "الطرف"},
}


def detect_language(text: str, client=None) -> dict:
    if client:
        try:
            prompt = f"""Detect the primary language of this text. Return JSON only:
{{"language": "string", "confidence": 0.0-1.0}}

Text sample: {text[:1000]}
"""
            result = _call_gemini_json(client, prompt)
            result["source"] = "ai"
            return result
        except Exception:
            pass

    return _detect_language_fallback(text)


def _detect_language_fallback(text: str) -> dict:
    words = set(re.findall(r"\w+", text.lower()))
    best_lang, best_overlap = "English", 0
    for lang, markers in COMMON_WORDS_BY_LANG.items():
        overlap = len(words & {m.lower() for m in markers})
        if overlap > best_overlap:
            best_lang, best_overlap = lang, overlap

    # crude script detection as a stronger signal than word overlap
    if re.search(r"[\u0600-\u06FF]", text):
        best_lang = "Urdu" if "می" in text or "کے" in text else "Arabic"

    confidence = 0.5 if best_overlap > 0 else 0.3
    return {"language": best_lang, "confidence": confidence, "source": "fallback"}
