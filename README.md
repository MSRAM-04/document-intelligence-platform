# Intelligent Document Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-green)](https://fastapi.tiangolo.com/)
[![EasyOCR](https://img.shields.io/badge/OCR-EasyOCR-orange)](https://github.com/JaidedAI/EasyOCR)

An AI-powered document extraction and validation platform supporting **Invoices**, **Balance Sheets**, **Profit & Loss Statements**, and **Cash Flow Statements**.

## Submission Links

The application is a single Render web service, so the frontend and backend base URL are the same. The service hostname below is the Render service created for this repository.

| Required item | URL / value |
|---|---|
| Deployed application / frontend URL | `https://document-intelligence-platform-wccy.onrender.com/` |
| Deployed backend API base URL | `https://document-intelligence-platform-wccy.onrender.com/api/v1` |
| Swagger/OpenAPI URL | `https://document-intelligence-platform-wccy.onrender.com/docs` |
| Public GitHub repository | `https://github.com/MSRAM-04/document-intelligence-platform` |
| Deployment platform | Render Web Service |
| Solution presentation | `docs/solution-presentation.pptx` |

### Submission checklist

- [ ] Solution presentation submitted.
- [ ] Frontend URL opens successfully.
- [ ] `GET /api/v1/health` returns `{"status":"ok"}`.
- [ ] `POST /api/v1/documents/process` accepts multipart PDF, JPG, and PNG uploads.
- [ ] `GET /api/v1/documents/{document_name}` returns the latest stored result.
- [ ] `GET /api/v1/documents` returns dashboard records.
- [ ] JSON output contains structured key-value fields, arrays, evidence, and validation checks.
- [ ] Invoice, balance sheet, profit and loss, and cash flow statement are supported.
- [ ] Scanned/image-based PDF, JPG, and PNG files are processed through OCR.
- [ ] Financial calculations are included in the JSON `validation.checks` section.
- [ ] Processed documents are stored in SQLite; Render uses the configured persistent disk.
- [ ] Input validation, logging, and exception handling are implemented.
- [ ] No secrets are stored in the repository; use `.env` locally and Render environment variables in production.
- [ ] README, architecture diagram, deployment URLs, and GitHub URL are included.

To ensure high stability and eliminate complex native engine installations (like Tesseract binaries), this platform uses **EasyOCR** (built on PyTorch deep learning models) and **PyMuPDF** (`fitz`).

---

## 🌟 Features

- **Document Validation**: Input control for PDF, JPG, PNG files, empty/corrupted check, and 3-page limit enforcement.
- **Deep-Learning OCR Engine**: EasyOCR spatial text extraction with bounding box layout sorting.
- **Complete Field & Table Extraction**:
  - **Invoice**: Invoice number, date, vendor, customer, subtotal, tax, total, currency, and line items table.
  - **Balance Sheet**: Assets, liabilities, equity, total capital & liabilities, comparative periods, and breakdown items.
  - **Profit & Loss**: Revenue, COGS, gross profit, operating expenses, net profit, and comparative periods.
  - **Cash Flow**: Operating, investing, financing cash flows, opening cash, net change (with negative bracket support like `(398.81)`), closing cash.
- **Grounding Evidence**: Returns `source_text`, `page_number`, and field `confidence` scores.
- **Financial Validation Engine**: Performs math checks for invoice line items/totals, balance sheet equations ($Assets \approx Liabilities + Equity$), P&L profit formulas, and cash flow reconciliations.
- **Persistent Database**: SQLite database for storing results and instant retrieval by document name or dashboard listing.
- **Interactive Web Dashboard**: Modern UI with document upload, status badges, key field cards, table views, validation check statuses, and raw JSON modal.

---

## Technology Stack and Design Choices

- **Backend**: Python 3.12, FastAPI, Pydantic, Uvicorn, SQLite3, repository pattern. FastAPI provides typed request handling and generated OpenAPI documentation with minimal operational overhead.
- **OCR & Vision**: Tesseract via `pytesseract`, PyMuPDF (`fitz`), and Pillow (`PIL`). Tesseract is installed by the Render build command for predictable CPU deployment.
- **Frontend**: HTML5, vanilla CSS, vanilla JavaScript. This keeps the dashboard lightweight and deployable from the same service as the API.
- **Testing**: Pytest, FastAPI TestClient.

---

## 🚀 Quickstart & Local Setup

### 1. Environment Setup
```bash
# Clone repository
git clone https://github.com/MSRAM-04/document-intelligence-platform.git
cd document-intelligence-platform

# Create virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run API & Frontend Application
```bash
# Start FastAPI application
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser at:
- **Interactive Web Dashboard**: `http://localhost:8000`
- **Swagger OpenAPI Docs**: `http://localhost:8000/docs`
- **API Health Check**: `http://localhost:8000/api/v1/health`

---

## 📡 REST API Specification

### 1. Process Document Upload
- **Endpoint**: `POST /api/v1/documents/process`
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `file`: Document file (`PDF`, `JPG`, or `PNG`).
  - `document_type`: `invoice` | `balance_sheet` | `profit_and_loss` | `cash_flow_statement`

### 2. Retrieve Document by Name
- **Endpoint**: `GET /api/v1/documents/{document_name}`
- **Response**: Latest structured JSON processing result.

### 3. List Processed Documents
- **Endpoint**: `GET /api/v1/documents`
- **Response**: Array of document metadata for the dashboard.

### 4. Health Check
- **Endpoint**: `GET /api/v1/health`

### Request examples

```bash
curl -X POST "http://localhost:8000/api/v1/documents/process" \
  -F "file=@sample.pdf;type=application/pdf" \
  -F "document_type=invoice"

curl "http://localhost:8000/api/v1/documents/sample.pdf"
curl "http://localhost:8000/api/v1/documents"
```

The upload response includes `extracted_data`, `validation`, `file_validation`, processing status, and grounding evidence. Financial rules use a $0.05 minimum absolute tolerance plus 1% relative tolerance, with the cash-flow change check allowing a $5,000 translation-difference tolerance.

## OCR, Models, and Confidence

PDF pages are rendered with PyMuPDF and images are read with Pillow. The deployed Render configuration uses Tesseract OCR because it is predictable on small instances and does not require a model download at request time. No paid external API or LLM is required. The extraction layer applies document-specific parsing rules over OCR text and returns field-level confidence and source evidence where available. Confidence is an extraction signal, not a guarantee of accounting correctness; the separate financial validation checks provide numerical consistency signals.

For a manually created Render service, use this exact build command so the Tesseract executable is installed:

```text
pip install -r requirements.txt && apt-get update && apt-get install -y tesseract-ocr
```

## Persistence and Deployment

Processed results are serialized as JSON in SQLite through the repository layer. Local development uses `data/documents.db`. The Render blueprint mounts a 1 GB persistent disk at `/var/data` and sets `DATABASE_PATH=/var/data/documents.db`; a Render plan that supports persistent disks is required for durable deployed history. `render.yaml` builds the service, starts Uvicorn, and serves the dashboard and API from one URL.

## Known Limitations

- OCR and first-time EasyOCR model loading can be slow and memory-intensive on small instances.
- Parsing is rule-based and optimized for the supplied document layouts; unusual layouts may produce missing fields or lower confidence.
- The current SQLite design is appropriate for a single service instance, not high-volume multi-instance writes.
- Uploads are limited to 20 MB and three pages per document.

## Production Improvements

For production scale, move persistence to PostgreSQL or object storage plus a metadata database, add authentication and tenant isolation, queue OCR work asynchronously, pin/download models during image build, add structured metrics and tracing, configure restrictive CORS and rate limits, and add automated deployment smoke tests.

---

## 🧪 Testing

Run the full test suite:
```bash
# Run pytest with pythonpath
pytest -o pythonpath=backend tests
```

Process the complete sample dataset:
```bash
python scripts/process_dataset.py
```

---

## 🏛️ Repository Structure

```
document-intelligence-platform/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/routes/documents.py
│   │   ├── core/ (config.py, database.py, logging.py)
│   │   ├── models/ (document.py)
│   │   ├── schemas/ (document.py, extraction.py)
│   │   ├── services/ (document_validation_service.py, ocr_service.py, extraction_service.py, financial_validation_service.py, document_service.py)
│   │   └── repositories/ (document_repository.py)
│   └── tests/
├── frontend/
│   ├── templates/ (dashboard.html, document_result.html)
│   ├── static/ (css/style.css, js/app.js)
│   └── index.html
├── docs/ (architecture.md)
├── sample_outputs/
├── scripts/ (process_dataset.py)
├── .env.example
├── .gitignore
└── README.md
```

---

## AI Coding Assistants Used

Document the tools used during implementation here before submission, for example: `GitHub Copilot` for code exploration, API/test changes, documentation, and presentation content. No credentials or API keys should be entered in this section.
