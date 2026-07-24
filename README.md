# ⚖️ JurisAI

### AI-Powered Contract Intelligence Platform

JurisAI is an AI-powered legal document intelligence platform that helps users analyze contracts efficiently using **Google Gemini AI**, **Retrieval-Augmented Generation (RAG)**, and a **persistent ChromaDB vector store**. It enables users to understand contracts, identify risks, detect and highlight missing clauses, compare agreements, search across their whole contract workspace, and generate professional, source-cited PDF reports — all behind a built-in login system.

---

## Features

- 📄 Contract Explanation
- ⚠️ Structured, Multi-Factor Risk Analysis (missing clauses, ambiguous wording, liability terms, payment terms, LLM reasoning) with a Confidence Score
- 📑 Missing Clause Detection with an in-document **Clause Highlighter** and ✔ / ✘ checklist
- 💬 Chat with Contract (RAG-based Question Answering) with **Source Citations** (page + paragraph)
- 🔎 Multi-Document Search across every contract in your workspace
- 📁 Multi-Format Support: PDF, DOCX, TXT, and scanned images (PNG/JPG) via **OCR**
- 🔍 Contract Comparison
- 📊 Analytics Dashboard: Risk Category Breakdown, Clause Distribution, Contract Health Score, Missing Clause Percentage, Risk Timeline
- 📥 PDF Report Generation (with citations, confidence, and structured scoring)
- 👤 Built-in Login (no external identity provider), per-user History, Saved Reports, and an Admin Dashboard
- 💾 Persistent Vector Database (ChromaDB) — documents remain searchable across restarts, not just within a session

---

## Technology Stack

| Category | Technology |
|----------|------------|
| Frontend | Streamlit |
| Backend | Python |
| Generative AI | Google Gemini API |
| Retrieval | RAG (Retrieval-Augmented Generation) |
| Vector Database | ChromaDB (persistent, local) |
| Document Parsing | pdfplumber, python-docx, pytesseract (OCR), pdf2image |
| Data Visualization | Plotly |
| Report Generation | ReportLab |
| Auth & History | SQLite (local, no external service) |
| Styling | Custom CSS |

---

## System Architecture

```
                User (Login)
                      │
                      ▼
             Streamlit Interface
                      │
   ┌──────────┬───────┼────────┬──────────┐
   ▼          ▼       ▼        ▼          ▼
 PDF/DOCX   Compare  Multi-Doc Analytics  Admin/
 TXT/OCR    Contracts  Search   Dashboard History
   │
   ▼
 Structured Chunking (page + paragraph metadata)
   │
   ▼
 ChromaDB Persistent Vector Store
   │
   ▼
 Semantic Retrieval (single doc or cross-document)
   │
   ▼
 Google Gemini AI
   │
   ▼
 Cited Answers, Structured Risk Score, Clause Checklist
   │
   ▼
 Dashboard & PDF Report (saved to History)
```

---

## Project Structure

```
JurisAI
│
├── auth/
│   └── auth_manager.py           # Login, registration, password hashing
│
├── backend/
│   └── gemini_helper.py
│
├── comparison/
│   └── contract_compare.py
│
├── document_processing/
│   └── file_extractor.py         # PDF / DOCX / TXT / OCR extraction with page+paragraph structure
│
├── embeddings/
│   └── embedding_model.py
│
├── rag/
│   ├── chunker.py                # Structured chunking with citation metadata
│   └── qa_chain.py                # Q&A with source citations
│
├── reports/
│   └── pdf_generator.py          # Structured PDF report (risk breakdown, clauses, citations)
│
├── risk_analysis/
│   ├── risk_analyzer.py          # Structured, multi-factor scoring + confidence
│   ├── missing_clause_detector.py
│   └── clause_highlighter.py     # In-text clause highlighting + checklist
│
├── storage/
│   ├── database.py               # SQLite schema (users, documents, reports, analysis_log)
│   └── history.py                # Document/report history + admin stats
│
├── styles/
│   ├── style.css
│   ├── sidebar.css
│   ├── dashboard.css
│   ├── cards.css
│   └── buttons.css
│
├── vector_store/
│   └── chroma_store.py           # Persistent, multi-document ChromaDB store
│
├── data/                         # SQLite DB (created on first run, gitignored)
├── chroma_data/                  # ChromaDB persistence (created on first run, gitignored)
├── generated_reports/            # Generated PDF reports (gitignored)
│
├── app.py
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Installation

Clone the repository

```bash
git clone https://github.com/Taruni9/JurisAI.git
```

Navigate to the project

```bash
cd JurisAI
```

Create a virtual environment

```bash
python -m venv venv
```

Activate the virtual environment

### Windows

```bash
venv\Scripts\activate
```

### macOS/Linux

```bash
source venv/bin/activate
```

Install Python dependencies

```bash
pip install -r requirements.txt
```

### System dependencies (required for OCR)

OCR support for scanned PDFs and images requires two system packages in addition to the Python ones:

**Ubuntu / Debian**
```bash
sudo apt-get install tesseract-ocr poppler-utils
```

**macOS (Homebrew)**
```bash
brew install tesseract poppler
```

**Windows**
Install the [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) installer and [poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases/), then add both to your PATH.

> If these aren't installed, every other feature still works — OCR simply won't be able to read scanned documents.

---

## Environment Variables

Create a `.env` file in the project root and add your Google Gemini API key.

```env
GOOGLE_API_KEY=your_api_key_here
```

> **Important:** Never commit your `.env` file or API keys to GitHub.

No other API keys or paid sign-ups are required — the vector database (ChromaDB) and the login/history system (SQLite) both run entirely locally.

---

## Running the Application

```bash
streamlit run app.py
```

The application will be available at:

```
http://localhost:8501
```

### First login

On first run, a default admin account is created automatically:

```
Username: admin
Password: admin123
```

Log in and change this, or create your own account from the "Create Account" tab. Anyone can self-register as a standard user; the `admin` role (and the Admin dashboard) is only granted to the first account.

---

## Workflow

1. Log in (or create an account)
2. Upload a contract — PDF, DOCX, TXT, or a scanned image
3. Generate a contract explanation
4. Detect missing clauses — see the ✔ / ✘ checklist and highlighted clauses in the document
5. Run risk analysis — see the overall score, confidence, and the four-factor breakdown
6. Ask questions about the document and see exactly which page/paragraph the answer came from
7. Search across every document in your workspace, not just the current one
8. Compare two contracts
9. View the analytics dashboard
10. Generate a PDF report (saved automatically to your History)
11. Revisit past documents and reports anytime from the History page
12. (Admins) View workspace-wide usage from the Admin dashboard

---

## Author

**Taruni**

GitHub: https://github.com/Taruni9

---

## Acknowledgements

- Google Gemini AI
- Streamlit
- Plotly
- ChromaDB
- Python Open Source Community
