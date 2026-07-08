# Grabbertoullie

This project is a full-stack Next.js and FastAPI web application that functions as a book retrieval agent. Accessed via a sleek web UI, the agent takes a command (e.g., "grab The Great Gatsby pdf"), uses the Groq LLM to parse the intent, searches multiple book sources in parallel for a direct download link, and provides the file to the user.

## Capabilities
- **Web Interface:** A sleek, modern chat interface built with Next.js and Tailwind CSS.
- **AI-Powered Search:** Leverages Groq to intelligently parse search requests, then searches several sources in parallel — Anna's Archive, Z-Library, Open Library, Project Gutenberg, Standard Ebooks, and Semantic Scholar — to find direct file links (PDF/EPUB).
- **SSRF Protection:** A secure backend proxy to download files safely, bypassing CORS issues on the frontend.
- **CLI Scrapers:** Standalone CLI tools for running direct book searches without the full application.

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+

### Setup

**1. Clone the repository**
```bash
git clone <repository_url>
cd <repository_dir>
```

**2. Configure Environment Variables**
Navigate to the `backend` folder and copy `.env.example` to `.env`:
```bash
cd backend
cp .env.example .env
```
Fill in your API keys in `backend/.env`. A Groq API key enables AI-powered query parsing; without it, the app falls back to a simple built-in metadata parser.

If you are changing the backend URL, you may also need to set `NEXT_PUBLIC_API_URL` in the frontend environment variables.

**3. Run the Backend (FastAPI)**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --host 0.0.0.0 --port 8001
```
The backend will run on `http://localhost:8001`.

**4. Run the Frontend (Next.js)**
In a new terminal window:
```bash
cd frontend
pnpm install
pnpm dev
```
The frontend will run on `http://localhost:3001` (or whichever port Next.js allocates if 3000/3001 are in use).

### Usage
Open your browser and navigate to the frontend URL (e.g. `http://localhost:3001`). Type a command in the chat to start searching for books!

## CLI Scraper Commands

The backend includes standalone CLI scripts to test the scraping logic directly from your terminal.

**Z-Library Scraper:**
Search for books directly on Z-Library.
```bash
cd backend
python zlib_scraper.py "Book title / author / ISBN" [--ext {epub,pdf,cbr,cbz,mobi,azw3,}] [--full]
```
- `query`: The book you want to search for.
- `--ext`: Optional file format filter.
- `--full`: Optional flag to also fetch the detail page and resolve the direct download URL.

**Anna's Archive Scraper:**
Search for books directly on Anna's Archive.
```bash
cd backend
python annas_archive.py "Book title / author / ISBN" [--ext {epub,pdf,cbr,cbz,}] [--full]
```
- `query`: The book you want to search for.
- `--ext`: Optional file format filter (defaults to epub).
- `--full`: Optional flag to also fetch the detail page and resolve the direct download URL.
