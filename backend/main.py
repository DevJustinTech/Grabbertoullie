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
import re

# explicitly load the .env from the backend/ directory so it is found regardless of cwd
backend_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(backend_dir, ".env"))

def extract_json_from_response(text: str) -> dict:
    if text is None:
        raise ValueError("Response text is None")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON block using regex
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # If no markdown block, try to find the first '{' and last '}'
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                # Pylance/Pyright in this version has a false positive with string slices and slice types.
                # Extracting it to a string var with a type ignore fixes the red squiggly.
                substr: str = text[start:end+1]  # type: ignore
                return json.loads(substr)
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from response")

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

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
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
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, headers=headers, content=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Serper API error: {e}")
            return {}

async def get_agent_response(user_message: str) -> dict:  # type: ignore[return]
    # Fallback response for missing API keys
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        return {
            "status": "success",
            "book_name": "Sample Book (Mock Result)",
            "file_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            "extension": "pdf"
        }

    system_prompt = """You are a highly advanced Book File Retrieval Agent. Your ultimate goal is to generate extremely thorough, advanced search queries (Google dorks) to pinpoint direct download URLs for books (PDF or EPUB), avoiding any generic or spammy sources.

COMMAND PARSING:
- Command format: "grab [Book Name] [filetype]"
- Normalize syntax, ignore misspellings or awkward phrasing.
- Extract the exact book name and desired file type (pdf or epub).

ADVANCED SEARCH STRATEGY:
- Generate heavily optimized Google dork queries to find globally exposed files, bypassing paywalls and landing pages.
- MUST Use advanced search operators. Examples to choose from:
  1. `intitle:"index of" "[book name]" (pdf|epub)`
  2. `"[book name]" filetype:[filetype] (site:archive.org/download OR site:vk.com OR site:github.com)`
  3. `"[book name]" ext:[filetype] "direct download"`
  4. `site:gutenberg.org/files "[book name]" [filetype]`
- AVOID generic terms like "buy", "kindle", "amazon", "goodreads", "scribd".
- Prioritize Open Directory listings, Archive.org raw file directories, and raw file hosting links.

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

First, decide on the ABSOLUTE BEST advanced search query to use, then I will provide the search results.
Return JSON ONLY, with a single key "search_query" containing your exact advanced query string."""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # Step 1: Get search query
    payload1 = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp1 = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload1)
            resp1.raise_for_status()
            res1_json = resp1.json()

            content1 = res1_json['choices'][0]['message'].get('content')
            if not content1:
                 # Fallback for models that might put json in a different key or return empty string
                 content1 = "{}"
            query_data = extract_json_from_response(content1)
            search_query = query_data.get("search_query", user_message)
        except Exception as e:
            content1_preview = locals().get('content1', 'No content')
            logger.error(f"Failed to get query from AI: {e}. Raw content: {content1_preview}")
            search_query = user_message

    # Step 2: Perform search
    search_results = await search_web(search_query)

    # Step 3: Parse results
    parse_prompt = f"""Here are the raw search results from the advanced query "{search_query}":
{json.dumps(search_results, indent=2)}

Deeply and thoroughly analyze these search results. Look aggressively for direct .pdf or .epub URLs.
- Look closely inside snippet texts, URLs, and titles.
- If a result links to archive.org/details/..., deduce and construct the archive.org/download/... link instead!
- Ignore generic landing pages. Only extract the absolute direct file URL.

Remember to output ONLY valid JSON in this precise format:
{{
 "status": "success",
 "book_name": "Corrected Book Title",
 "file_url": "https://url.com/direct_file.pdf",
 "extension": "pdf"
}}
Or if TRULY not found after exhaustive check:
{{
 "status": "fail",
 "reason": "Explanation of the failure."
}}"""

    payload2 = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": f'{{"search_query": "{search_query}"}}'},
            {"role": "user", "content": parse_prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp2 = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload2)
            resp2.raise_for_status()
            res2_json = resp2.json()

            content2 = res2_json['choices'][0]['message'].get('content')
            if not content2:
                 content2 = "{}"
            final_data = extract_json_from_response(content2)
            if not final_data or "status" not in final_data:
                return {"status": "fail", "reason": f"AI output was missing 'status' key. Data: {final_data}"}
            return final_data
        except httpx.HTTPStatusError as e:
            logger.error(f"Groq HTTP Error: {e}")
            return {"status": "fail", "reason": f"Groq API Error: {e.response.status_code} {e.response.text}"}
        except Exception as e:
            res_preview = locals().get('res2_json', 'No JSON parsed')
            logger.error(f"Failed to parse final JSON from AI: {repr(e)}. Raw res2_json: {res_preview}")
            return {"status": "fail", "reason": f"Internal Processing Error: {repr(e)}"}

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
                async with httpx.AsyncClient(timeout=60.0) as client:
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
    async with httpx.AsyncClient(timeout=60.0) as client:
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
    async with httpx.AsyncClient(timeout=60.0) as client:
        await client.post(url, headers=headers, json=payload)

if __name__ == "__main__":
    import uvicorn  # type: ignore
    uvicorn.run(app, host="0.0.0.0", port=8001)
