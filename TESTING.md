# Testing report (TrustGuard AI 4.1)

Environment where tests were run: Linux sandbox, Python 3.12.3, Streamlit 1.67.0, pandas 3.0.6, numpy 2.5, PyMuPDF (current), faiss-cpu 1.15.1, rank-bm25, pytest.

## Result: `python -m pytest` → **79 passed** (final run, ~5 s)

| File | Tests | Covers |
|---|---|---|
| `test_utils_security.py` | 14 | CSV formula neutralisation, Markdown image/link neutralisation, HTML escaping, all 11 original patterns still present, every rule fires, line-break handling, masked secrets, cautious wording, Security Lab cases (13 PASS / 2 REVIEW by design) |
| `test_db.py` | 5 | logging/reading, hash-only storage (raw secret absent from the DB file), parameterised SQL, a Phase 4-schema database with an old record is preserved, DB errors don't crash |
| `test_documents_retrieval.py` | 26 | PDF extraction + page numbers, empty / non-PDF / corrupt / encrypted / image-only / blank PDFs, size limit, chunking, page rendering + highlight, FAISS vector, BM25, hybrid RRF, tiny corpora, k > corpus, empty queries, query embedded once for 3 methods, Precision/Recall/MRR, label parsing, BOM CSV, validation, full experiment run |
| `test_llm.py` | 19 | prompt hardening, evidence-only mode, Ollama connection / timeout / missing-model / empty / malformed handling (mocked HTTP), insufficient-evidence paths, reliability heuristics, judge parsing and failure modes, Ollama status |
| `test_app_flows.py` | 15 | Streamlit `AppTest` end-to-end: all six pages render; empty dashboard shows empty states; Q&A flow with real FAISS/BM25/RRF; source button → real PDF preview; remove-document and clear-conversation state; validation messages; LLM answer → claim check bound to its own answer; Ollama-down fallback; injection in question is flagged and logged; document-scan events not duplicated and no document text logged; dashboard values reflect DB/session; Security Monitor scan; Security Lab run + logging; stale Phase 3 warning |

Also done: the real Streamlit server was started (`streamlit run app.py --server.headless true`); `/_stcore/health` returned `ok` and `/` returned HTTP 200 with no errors in the log.

Mutation check: reverting to stock BM25 made `test_bm25_positive_scores_on_tiny_corpora` fail (good). Removing the clearing of answers inside `rebuild_index` did **not** fail any test, because a second defensive check on the Q&A page also discards answers from a different document set; the behaviour is protected twice.

Bug found by the tests during development: CSV formula neutralisation silently did nothing on pandas 3 string columns. Fixed.

## NOT tested here, and why
| Item | Reason |
|---|---|
| **Real `all-MiniLM-L6-v2` embeddings and the `sentence-transformers` package** | `huggingface.co` is unreachable in the sandbox and the package was not installed. Tests use a deterministic hashed bag-of-words stand-in; FAISS, BM25 and RRF ran for real, but retrieval *quality* with the real model is unmeasured. The `encode(...)` call arguments are the same as in Phase 4. |
| **Real Ollama generation and the real judge** | Ollama is not available here. Request/response handling was tested with mocked HTTP only; prompt quality and the model's real behaviour are untested. |
| **Visual appearance / responsive layout / dark sidebar** | No browser is available, so there are no screenshots. The CSS and `[theme.sidebar]` config were written carefully but are visually unverified; some Streamlit CSS selectors differ between versions. Please look at every page once. |
| **Real drag-and-drop upload and CSV upload widgets** | `AppTest` cannot drive `st.file_uploader`. Upload processing was tested by calling the same `process_upload` function; the CSV pipeline by calling its functions directly. |
| **Streamlit 1.40–1.66, Python 3.10/3.11, macOS** | Only Streamlit 1.67 / Python 3.12 / Linux were run. |
| **Performance on large PDFs** | Not measured. |
