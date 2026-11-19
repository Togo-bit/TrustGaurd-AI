# TrustGuard AI 4.1

**Upload PDFs, ask questions in plain English, and see exactly which pages each answer came from.**

TrustGuard AI is a document Q&A app that does not just answer: it shows its evidence, scores how well the answer matches that evidence, and scans documents, questions and answers for prompt-injection attempts and sensitive data. Your documents are processed locally; the only download is the embedding model on first use.

Under the hood it combines Sentence Transformers + FAISS + BM25 + Reciprocal Rank Fusion (RRF) for retrieval and a local Ollama model for answers, with a security monitor and two evaluation labs, all in a Streamlit app that runs entirely on your machine. This is an **academic prototype, not a production security boundary**.

**Contents:** [Screenshots](#screenshots) · [Features](#features) · [Architecture and data flow](#architecture-and-data-flow) · [Tech stack](#tech-stack) · [Run on macOS with VS Code](#run-on-macos-with-vs-code) · [Project layout](#project-layout) · [Retrieval evaluation CSV](#retrieval-evaluation-csv-phase-3) · [Reliability signals](#reliability-signals-and-claim-support-check) · [Security notes](#security-notes)

## Screenshots

### Document Q&A
Ask a question about your uploaded PDFs and get an answer built from the retrieved passages. Each answer is shown with its mode badge, cited sources you can open as PDF pages, reliability signals and the retrieved evidence.

![Document Q&A page showing a question and the answer retrieved from the uploaded document](document.png)

### Dashboard
A live overview of indexed documents, questions analyzed and security findings, with quick actions, recent activity and an events-by-severity chart. The sidebar shows the app's pages and the local Ollama model status.

![TrustGuard AI dashboard with summary cards, quick actions and recent activity](dashboard.png)

### Security Monitor
Every logged event can be filtered by severity and event type, or searched by text and rule ID. Each event stores a short `content_hash` instead of the scanned text.

![Security Monitor event log with severity and event-type filters](security-monitor.png)

### Event charts
Events grouped by type and by day, built from the same local event log.

![Charts of events by type and events per day](event-charts.png)

## Features

**Document Q&A**
- **Multi-PDF upload.** Upload several text-based PDFs; each is split into page-tagged chunks and indexed locally. Scanned/image-only PDFs are not supported (no OCR).
- **Three retrieval strategies.** Choose vector search (FAISS), keyword search (BM25) or hybrid (both fused with Reciprocal Rank Fusion), and set how many passages (k, 1-10) to retrieve.
- **Grounded, cited answers.** A local Ollama model answers using only the retrieved excerpts and cites each claim as `[Source: file.pdf, page N]`. If the evidence is too weak, the app says so instead of answering.
- **Works without an LLM.** If Ollama is not running, the app falls back to showing the retrieved excerpts verbatim (evidence-only mode).
- **Evidence you can inspect.** Every answer lists the retrieved passages with their scores and ranks, and you can open the cited PDF page with the matching text highlighted.
- **Reliability signals.** Top semantic similarity, citation coverage, evidence overlap and a check that every citation points to a passage that was actually retrieved (heuristics, not hallucination detection).
- **Claim-support check (on demand).** A local Ollama model splits the answer into claims and judges whether the retrieved text supports each one.
- **Conversation history.** The most recent earlier questions and answers in the session stay available for review.

**Security**
- **Pattern scanning.** 11 rules (6 prompt-injection/jailbreak, 5 sensitive-data) scan uploaded documents, your questions and generated answers. Findings are *potential* findings with an explanation and a typical false-positive caveat; sensitive matches are masked in the UI.
- **Security Monitor.** Review the events the app has logged in a table (id, timestamp, severity, event type, details, content hash). Filter by severity or event type, or search by text such as a file name or rule ID like `INJ-01`. Events store a short hash of the scanned content, never the text.

**Evaluation**
- **Phase 3 Evaluation Lab.** Upload a CSV of questions with labelled relevant pages and compare the three retrieval methods using Precision@k, Recall@k and MRR (see *Retrieval evaluation CSV* below).
- **Phase 4 Security Lab.** Run 15 built-in test cases against the scanner: core detections, false-positive checks and documented known limitations (paraphrased and obfuscated attacks that intentionally show REVIEW).

**Overview pages**
- **Dashboard.** Summary cards (documents indexed, questions analyzed, security findings, high-severity findings), quick actions (upload documents, scan text, retrieval evaluation, run security tests), recent activity and events by severity.
- **About & Limitations.** Background on the project and what it does not do.
- **Model status.** The sidebar shows whether Ollama is reachable and the configured model (for example `llama3.2`) is ready.

## Architecture and data flow

TrustGuard AI is a single Streamlit app. `app.py` routes between pages in `views/`; each page calls into the `trustguard/` package, which holds the logic (retrieval, LLM calls, scanning, storage). Everything runs locally: the embedding model runs in-process, and the LLM is a local Ollama server.

```mermaid
flowchart TD
    subgraph IDX["1. Indexing (once per document)"]
        A["PDF upload"] --> B["Extract text per page"]
        B --> C["Split into page-tagged chunks"]
        B --> S1["Security scan of each page"]
        C --> D["Embed chunks<br/>Sentence Transformers, L2-normalised"]
        D --> E["FAISS index<br/>inner product = cosine"]
        C --> F["BM25 index<br/>Lucene-style IDF"]
    end

    subgraph ASK["2. Answering a question"]
        Q["User question"] --> S2["Security scan of question"]
        Q --> R["Retrieve top-k chunks"]
        E --> R
        F --> R
        R --> G{"Enough evidence?"}
        G -- "no" --> INS["Insufficient-evidence message"]
        G -- "yes, Ollama off" --> EV["Evidence-only: verbatim excerpts"]
        G -- "yes, Ollama on" --> L["Ollama answer with citations"]
        L -- "Ollama error" --> EV
        L --> S3["Security scan of answer"]
    end

    subgraph REV["3. Review"]
        L --> REL["Reliability signals"]
        L --> J["Optional claim-support check<br/>Ollama as judge"]
        R --> PV["Evidence list and PDF page preview"]
    end

    S1 --> DB[("Local SQLite event log")]
    S2 --> DB
    S3 --> DB
    DB --> MON["Security Monitor and Dashboard"]
```

### Step by step

**1. Indexing** (when you upload a PDF)
1. Text is extracted page by page and split into chunks that keep their source file and page number, which is what makes page-level citations possible.
2. Each page is scanned by the security rules, and the document is badged with its number of potential findings.
3. Chunks are embedded once with the Sentence Transformers model (`all-MiniLM-L6-v2`) into L2-normalised vectors and reused afterwards.
4. Two indexes are built over the chunks: a FAISS flat inner-product index (cosine similarity on normalised vectors) and a BM25 keyword index. The BM25 uses a Lucene-style IDF that is never negative, because the stock `rank_bm25` IDF can rank keyword matches below non-matches on very small corpora.

**2. Answering a question** (when you click *Analyze question*)
1. The question is scanned by the security rules; any findings are logged.
2. **Retrieval** uses the strategy you chose:

   | Strategy | How chunks are ranked |
   |---|---|
   | Vector | Cosine similarity between the question embedding and each chunk |
   | BM25 | Keyword relevance; chunks with no query-term match are not returned |
   | Hybrid | Reciprocal Rank Fusion: each chunk scores `1/(c + vector_rank)` plus `1/(c + bm25_rank)` if it had a keyword match, where `c` is `RRF_CONSTANT` in `trustguard/config.py` |

   RRF combines *ranks* rather than raw scores because cosine similarity and BM25 scores are on incompatible scales. Query embeddings and scores are cached per question, so comparing methods embeds each question only once.
3. **Evidence gate.** The app refuses to answer only if the best passage has very low semantic similarity (below `MIN_EVIDENCE_COSINE`) *and* none of the retrieved passages had a keyword match.
4. **Generation.** Retrieved chunks are wrapped in `<document_excerpt>` tags and sent to Ollama with a system prompt that tells the model to use only those excerpts, to treat them as untrusted data and never follow instructions inside them, to cite `[Source: file, page N]`, and to reply with a fixed "insufficient evidence" phrase when the excerpts do not answer the question. Tag-like text inside documents is neutralised so a document cannot close or reopen the excerpt tags.
5. The result is one of four modes: `llm` (Ollama answer), `evidence_only` (LLM turned off), `fallback` (Ollama failed, excerpts shown instead) or `insufficient`.
6. Answer text from the `llm` and `insufficient` modes is scanned again, and findings are logged as output-scan events.

**3. Review** (what you see on the page)
- The answer with its mode badge, plus clickable source buttons that open the cited PDF page with matching text highlighted.
- Reliability signals computed from the answer and the retrieved text (see *Reliability signals and claim-support check* below).
- The retrieved evidence with vector score, BM25 score and ranks for each chunk.
- An optional claim-support check, which sends the answer and the retrieved text to Ollama in JSON mode and reports how many claims were judged supported.

## Tech stack

Versions are the minimums required in `requirements.txt` (and `requirements-dev.txt` for pytest); pip installs the newest release that satisfies them.

| Technology | Version | Role in TrustGuard AI | Why it is used |
|---|---|---|---|
| Python | 3.10–3.12 | Application language | Range supported by the setup steps below |
| [Streamlit](https://streamlit.io) | ≥ 1.40 | Web UI, session state, file upload | Pure-Python interface, no separate frontend code |
| [PyMuPDF](https://pymupdf.readthedocs.io) | ≥ 1.24.3 | PDF text extraction, page rendering, passage highlighting | First release to expose the `pymupdf` module name; also renders the page images shown in the preview |
| [Sentence Transformers](https://www.sbert.net) | ≥ 3.0 | Embeds chunks and questions into vectors | Simple API for local embedding models |
| `all-MiniLM-L6-v2` (model) | n/a | The embedding model: 384-dimensional vectors, English, Apache 2.0 | Small and fast on CPU (~90 MB download), runs fully locally |
| [FAISS](https://github.com/facebookresearch/faiss) (`faiss-cpu`) | ≥ 1.8.0 | Vector search (`IndexFlatIP`, cosine on normalised vectors) | Exact similarity search with no GPU needed |
| [rank-bm25](https://pypi.org/project/rank-bm25/) | ≥ 0.2.2 | Keyword search (BM25Okapi with a Lucene-style IDF override) | Lightweight BM25 that can be subclassed |
| Reciprocal Rank Fusion | n/a (algorithm) | Merges the vector and keyword rankings into one hybrid ranking | Combines ranks, so incompatible score scales do not matter |
| [Ollama](https://ollama.com) + `llama3.2` | Ollama not pinned; `llama3.2` default tag is the 3B model (~2 GB download) | Local LLM for answers and the claim-support check | Runs on your machine, so no document is sent to a cloud API. Override the model with `OLLAMA_MODEL` |
| `requests` | ≥ 2.32 | HTTP calls to the Ollama API | Standard HTTP client |
| NumPy | ≥ 1.26 | Vector and score arrays | Required by FAISS and the retrieval code |
| pandas | ≥ 2.2 | Tables for results, events and CSV evaluation | Data handling for the monitor and evaluation labs |
| Plotly | ≥ 5.24 | Interactive charts | Charts in the Dashboard and Security Monitor |
| SQLite (`sqlite3`, standard library) | bundled with Python | Local security-event log | No extra install; stores only content hashes |
| pytest | ≥ 8.0 (dev only) | Unit tests | Standard Python test runner |

**Licensing note:** PyMuPDF is dual-licensed (open-source AGPL or a commercial licence from Artifex), so check its terms before distributing or hosting a modified version of this app.

## Run on macOS with VS Code

**1. Prerequisites** (Terminal):
```bash
brew install python@3.12      # Python 3.10–3.12 all work; skip if already installed
brew install --cask ollama    # or download from https://ollama.com
```

**2. Environment** (open the project folder in VS Code, then *Terminal ▸ New Terminal*):
```bash
cd TrustGuardAI_Phase4
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
In VS Code: *Cmd+Shift+P ▸ Python: Select Interpreter ▸ `.venv`*.

**3. Ollama model** (open the Ollama app, or run `ollama serve` in a separate terminal):
```bash
ollama pull llama3.2
```
Use another model with `export OLLAMA_MODEL=mistral` before starting the app.

**4. Start**
```bash
python -m streamlit run app.py
```
Open http://localhost:8501. The **first** document upload downloads the embedding model (`all-MiniLM-L6-v2`, ~90 MB) so it needs internet once; afterwards it is cached.

**5. Run the tests** (optional)
```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

### Troubleshooting
| Symptom | Fix |
|---|---|
| Sidebar shows "Ollama not reachable" | Open the Ollama app or run `ollama serve`. Without it the app still works in evidence-only mode. |
| "Model 'llama3.2' not installed" | `ollama pull llama3.2` (or set `OLLAMA_MODEL`), then click *Refresh status* in the sidebar. |
| Answers time out | First request loads the model. Raise `OLLAMA_TIMEOUT` (seconds, default 180) or use a smaller model. |
| "Could not create embeddings" on first upload | The embedding model must be downloaded once; check your internet connection. |
| "No extractable text" | The PDF is a scan/image. OCR is not included. |
| `faiss` or `torch` fails to install | Use Python 3.10–3.12 (not 3.13+). On Apple Silicon use a native arm64 Python. |
| Port already in use | `python -m streamlit run app.py --server.port 8502` |
| Change limits | `MAX_FILE_MB` etc. are in `trustguard/config.py`; keep `server.maxUploadSize` in `.streamlit/config.toml` in sync. |

Environment variables: `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_NUM_CTX`, `TRUSTGUARD_DB`.

## Project layout
```
app.py                 entry point: sidebar navigation + routing
views/                 one module per page (dashboard, qa, security_monitor, eval_lab, security_lab, about)
trustguard/            core logic, no Streamlit imports in most modules so it is unit-testable
  config.py  db.py  security.py  documents.py  retrieval.py  llm.py  evaluation.py  utils.py
  state.py  ui.py      (Streamlit session state, theme/CSS and shared components)
tests/                 pytest suite
.streamlit/config.toml theme, 20 MB upload cap, telemetry off
```

## Retrieval evaluation CSV (Phase 3)
Required columns: `question`, `relevant_passages`. Write relevant pages as `paper.pdf|2;paper.pdf|5` (original PDF page numbers; filenames must match the indexed PDFs exactly). A template is downloadable in the app. Excel/Numbers exports (UTF-8 BOM) are accepted.

- Precision@k = relevant pages returned / distinct pages returned in the top-k chunks
- Recall@k = relevant pages returned / labelled relevant pages
- MRR = 1 / rank of the first relevant page among the distinct returned pages (0 if none)

A page returned by several chunks counts once. Labels that name unknown files or pages outside the PDF cause the row to be skipped with a message; a label for a real page without extractable text is kept and counts against recall.

## Reliability signals and claim-support check
These are heuristics, **not hallucination detection**:
- *Top semantic similarity*: best cosine similarity between question and a retrieved passage.
- *Citation coverage*: share of substantive answer sentences carrying a `[Source: file, page N]` marker. Citations that point to a source/page that was not retrieved are flagged.
- *Evidence overlap*: share of the answer's content words (stopwords/citations removed) that occur in the retrieved text. Lexical only.
- *Claim-support check*: a local Ollama model judges each claim against the retrieved text. It can be wrong; sample claims manually.

## Security notes
Pattern scanning (11 rules, IDs `INJ-01…06`, `SEC-01…05`) reports *potential findings* only. It misses paraphrased/obfuscated attacks (the Security Lab includes two such cases that intentionally show REVIEW) and can flag harmless text. Events store a short hash of the scanned content, never the text. Do not upload confidential documents or real credentials.
