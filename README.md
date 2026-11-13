# TrustGuard AI 4.1

Local document-grounded Q&A (Sentence Transformers + FAISS + BM25 + RRF + Ollama) with security monitoring and two evaluation labs. Streamlit app, runs entirely on your machine. This is an **academic prototype, not a production security boundary**.

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
