# WhatsApp Book Retrieval Web Agent

This project is a rewrite of an n8n WhatsApp agent into a full-stack Next.js and FastAPI web application. It functions as a chatbot that takes a command (e.g., "grab The Great Gatsby pdf"), uses OpenRouter LLM to parse the intent, searches the web via Serper API for a direct download link, and provides the file to the user.

## Features
- **Web Interface:** A sleek chat interface built with Next.js and Tailwind CSS.
- **WhatsApp Integration:** Built-in webhooks to connect to Meta's WhatsApp Cloud API. Automatically sends small files (<45MB) as direct document messages, or provides the URL for larger files.
- **AI-Powered Search:** Leverages OpenRouter and Serper to intelligently find direct file links (PDF/EPUB) from sites like Internet Archive and Gutenberg.
- **SSRF Protection:** A secure backend proxy to download files safely, bypassing CORS issues on the frontend.

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
Fill in your API keys in `backend/.env`. (OpenRouter and Serper API keys are required for full functionality).

**3. Run the Backend (FastAPI)**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001
```
The backend will run on `http://localhost:8001`.

**4. Run the Frontend (Next.js)**
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
The frontend will run on `http://localhost:3001`.

### Usage
Open your browser and navigate to `http://localhost:3001`. Type a command in the chat to start searching for books!