# pyre-ignore-all-errors
from fastapi import FastAPI, Request, HTTPException, Response  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from pydantic import BaseModel  # type: ignore
import httpx  # type: ignore
import os
import json
import logging
import socket
import ipaddress
from typing import Tuple
from urllib.parse import urlparse
from dotenv import load_dotenv  # type: ignore

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

class ChatRequest(BaseModel):
    message: str

async def search_web(query: str) -> dict:  # type: ignore[return]
    # Use dummy data if API key is missing
    if not SERPER_API_KEY or SERPER_API_KEY == "your_serper_api_key_here":
        return {
            "organic": [
                {
                    "title": "Download Book PDF",
                    "link": "https://example.com/book.pdf"
                }
            ]
        }

    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query})
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, content=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Serper API error: {e}")
            return {}

async def get_agent_response(user_message: str) -> dict:  # type: ignore[return]
    # Fallback response for missing API keys
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
        return {
            "status": "success",
            "book_name": "Sample Book (Mock Result)",
            "file_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            "extension": "pdf"
        }

    system_prompt = """You are a File Retrieval Agent. Your job is to find a DIRECT download URL for a book (PDF or EPUB) based on a user's command.

COMMAND PARSING:
- Command format: "grab [Book Name] [filetype]"
- Normalize messy spacing or underscores in book names
- Extract the book name and desired file type (pdf or epub)

SEARCH STRATEGY:
- Formulate search queries to find direct download links, such as:
  1. "[book name] [filetype] direct download"
  2. "[book name] filetype:[filetype] site:archive.org OR site:gutenberg.org"
  3. "[book name] [filetype] free download"
- Prioritize results from: Project Gutenberg, Internet Archive, Open Library, academic repositories
- AVOID: Amazon, Google Books, Scribd, preview/landing pages

OUTPUT FORMAT:
You must output ONLY valid JSON:
{
 "status": "success",
 "book_name": "Corrected Book Title",
 "file_url": "https://direct-download-url.com/file.pdf",
 "extension": "pdf"
}

If no direct download found:
{
 "status": "fail",
 "reason": "Explanation of why no link was found"
}

First, decide on a search query to use, then I will provide the search results.
Return JSON ONLY, with a single key "search_query" containing your query."""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:8001",
        "Content-Type": "application/json"
    }

    # Step 1: Get search query
    payload1 = {
        "model": "meta-llama/llama-3-8b-instruct:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient() as client:
        try:
            resp1 = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload1)
            resp1.raise_for_status()
            res1_json = resp1.json()

            content1 = res1_json['choices'][0]['message']['content']
            query_data = json.loads(content1)
            search_query = query_data.get("search_query", user_message)
        except Exception as e:
            logger.error(f"Failed to get query from AI: {e}")
            search_query = user_message

    # Step 2: Perform search
    search_results = await search_web(search_query)

    # Step 3: Parse results
    parse_prompt = f"""Here are the search results for the query "{search_query}":
{json.dumps(search_results, indent=2)}

Analyze these results and extract a direct download URL.
Remember to output ONLY valid JSON in this format:
{{
 "status": "success",
 "book_name": "Corrected Book Title",
 "file_url": "https://direct-download-url.com/file.pdf",
 "extension": "pdf"
}}
Or if not found:
{{
 "status": "fail",
 "reason": "Explanation"
}}"""

    payload2 = {
        "model": "meta-llama/llama-3-8b-instruct:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": f'{{"search_query": "{search_query}"}}'},
            {"role": "user", "content": parse_prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient() as client:
        try:
            resp2 = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload2)
            resp2.raise_for_status()
            res2_json = resp2.json()

            content2 = res2_json['choices'][0]['message']['content']
            final_data = json.loads(content2)
            return final_data
        except Exception as e:
            logger.error(f"Failed to parse final JSON from AI: {e}")
            return {"status": "fail", "reason": "Could not extract download link from search results."}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    result = await get_agent_response(request.message)
    return result

def is_valid_url(url: str) -> Tuple[bool, str]:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False, "Invalid URL scheme. Only HTTP and HTTPS are allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL format."

        # Optional: Resolve hostname to IP and check if it's public.
        # This prevents accessing localhost or internal networks.
        # Since resolving every time can be complex asynchronously, we block obvious local IPs.
        try:
            ip = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_link_local:
                return False, "Invalid or restricted URL domain/IP."
        except socket.gaierror:
            pass  # DNS resolution failed, might still be valid or handled by httpx later

        return True, ""
    except Exception as e:
        return False, str(e)

@app.get("/api/download")
async def download_endpoint(url: str):
    valid, reason = is_valid_url(url)
    if not valid:
        raise HTTPException(status_code=400, detail=reason)

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

            headers: dict[str, str] = dict(response.headers)
            # Remove transfer-encoding as we're reading the whole content
            headers.pop("transfer-encoding", None)

            # Suggest a filename from the URL
            filename = url.split("/")[-1]
            if not filename:
                filename = "downloaded_file"

            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

            return Response(content=response.content, status_code=response.status_code, headers=headers)
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            return Response(content=challenge, status_code=200)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    return Response(content="Hello", status_code=200)

@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.json()

    if body.get("object") == "whatsapp_business_account":
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])

                for message in messages:
                    if message.get("type") == "text":
                        user_phone = message.get("from")
                        text = message.get("text", {}).get("body", "")

                        # Process message asynchronously
                        # In a production environment, you might want to use a task queue here
                        import asyncio
                        asyncio.create_task(process_whatsapp_message(user_phone, text))

        return Response(content="EVENT_RECEIVED", status_code=200)
    else:
        raise HTTPException(status_code=404, detail="Not Found")

async def process_whatsapp_message(phone_number: str, text: str):
    logger.info(f"Processing message from {phone_number}: {text}")
    try:
        result = await get_agent_response(text)

        if result.get("status") == "success":
            file_url: str = result.get("file_url", "")
            book_name: str = result.get("book_name", "Unknown")
            extension: str = result.get("extension", "pdf")

            if not file_url:
                await send_whatsapp_text(phone_number, "Sorry, no download URL was found.")
                return

            # Check file size if possible, or attempt to download and send
            # For simplicity, we'll try to get the headers first to check size
            try:
                async with httpx.AsyncClient() as client:
                    head_resp = await client.head(file_url, follow_redirects=True)
                    content_length = int(head_resp.headers.get("content-length", 0))

                    # If less than ~45MB, try sending as document
                    if 0 < content_length < 45 * 1024 * 1024:
                        await send_whatsapp_document(phone_number, file_url, f"{book_name}.{extension}")
                    else:
                        # Too large or unknown size, send link
                        msg = f"Found '{book_name}'!\n\nThe file might be too large to send directly on WhatsApp. You can download it here:\n{file_url}"
                        await send_whatsapp_text(phone_number, msg)
            except Exception as e:
                logger.warning(f"Could not HEAD file, sending link instead: {e}")
                msg = f"Found '{book_name}'!\n\nDownload link:\n{file_url}"
                await send_whatsapp_text(phone_number, msg)

        else:
            reason = result.get("reason", "Could not find the book.")
            msg = f"Sorry, I couldn't find a direct download link.\n\nReason: {reason}"
            await send_whatsapp_text(phone_number, msg)

    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {e}")
        await send_whatsapp_text(phone_number, "Sorry, an error occurred while processing your request.")

async def send_whatsapp_text(to: str, text: str):
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json=payload)

async def send_whatsapp_document(to: str, document_url: str, filename: str):
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": {
            "link": document_url,
            "filename": filename
        }
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json=payload)

if __name__ == "__main__":
    import uvicorn  # type: ignore
    uvicorn.run(app, host="0.0.0.0", port=8001)
