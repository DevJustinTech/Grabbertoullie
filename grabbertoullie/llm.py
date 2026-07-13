import os
import json
import re
import logging
# pyre-ignore[21]
import httpx
from typing import Dict, Any

from .security import check_url_hook

logger = logging.getLogger(__name__)

_shared_client: httpx.AsyncClient | None = None

def get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(timeout=60.0, event_hooks={"request": [check_url_hook]})
    return _shared_client

JSON_BLOCK_RE = re.compile(r'```(?:json)?\s*(.*?)\s*```', re.DOTALL)

def extract_json_from_response(text: str) -> dict:
    if text is None:
        raise ValueError("Response text is None")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON block using regex
        match = JSON_BLOCK_RE.search(text)
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
                substr: str = text[start:end+1]  # type: ignore
                return json.loads(substr)
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from response")

def _fallback_extract(user_message: str) -> Dict[str, Any]:
    user_message = user_message.strip()

    is_exact = False
    if "[exact]" in user_message.lower():
        is_exact = True
        # Remove [exact] case-insensitively
        user_message = re.sub(r'\[exact\]', '', user_message, flags=re.IGNORECASE).strip()

    # Try to extract format at the end. Default to "any" so a query with no
    # explicit format isn't silently narrowed to PDF (which hides EPUB-only
    # books — a large share of modern fiction on these sources).
    fmt = "any"
    msg_lower = user_message.lower()
    if msg_lower.endswith(" pdf"):
        fmt = "pdf"
        user_message = user_message[:-4].strip()
    elif msg_lower.endswith(" epub"):
        fmt = "epub"
        user_message = user_message[:-5].strip()

    # Try to strip common command prefixes
    prefixes = ["grab ", "find ", "get ", "search for ", "download "]
    msg_lower_now = user_message.lower()
    for prefix in prefixes:
        if msg_lower_now.startswith(prefix):
            user_message = user_message[len(prefix):].strip()
            break

    title = user_message
    return {
        "title": title,
        "author": "",
        "year": "",
        "format": fmt,
        "fuzzy": False if is_exact or title else True
    }

async def extract_metadata_from_query(user_message: str, groq_api_key: str) -> Dict[str, Any]:
    """
    Uses the LLM to extract structured metadata from the user's query.
    """
    is_exact = False
    if "[exact]" in user_message.lower():
        is_exact = True
        user_message = re.sub(r'\[exact\]', '', user_message, flags=re.IGNORECASE).strip()

    if not groq_api_key or groq_api_key == "your_groq_api_key_here":
        # Fallback dummy metadata. We pass the modified user_message without [exact]
        metadata = _fallback_extract(user_message)
        if is_exact:
            metadata["fuzzy"] = False
        return metadata

    system_prompt = """You are a precise Book Metadata Extraction Agent.
Your job is to analyze a user's request for a book and extract structured metadata.

CRITICAL INSTRUCTIONS:
- You MUST rigorously separate the book title from the author name. If the user says "Harry Potter by JK Rowling", the title is EXACTLY "Harry Potter" and the author is "JK Rowling". Do not include "by JK Rowling" in the title field!
- If the user provides a series name but no specific book, treat the series name as the title.

Extract the following fields:
- title: The EXACT title of the book, stripped of the author's name and unnecessary punctuation.
- author: The author of the book (if mentioned).
- year: The publication year (if mentioned).
- format: The preferred file format ('pdf', 'epub', or 'any'). Defaults to 'any' if the user does not clearly request a specific format.
- fuzzy: true or false. Set to true if the query is ambiguous, missing an author, has a partial title, or is a vague description. Set to false if it's a very specific, exact request with title and author.

OUTPUT FORMAT:
You must output ONLY valid JSON in this exact structure:
{
  "title": "Exact Book Title",
  "author": "Author Name",
  "year": "1984",
  "format": "any",
  "fuzzy": false
}
"""

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        client = get_shared_client()
        resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        res_json = resp.json()

        content = res_json['choices'][0]['message'].get('content')
        if not content:
             content = "{}"

        metadata = extract_json_from_response(content)

        # Ensure required fields exist
        if "title" not in metadata:
            metadata["title"] = user_message
        if "format" not in metadata:
            metadata["format"] = "any"
        if "fuzzy" not in metadata:
            metadata["fuzzy"] = True

        if is_exact:
            metadata["fuzzy"] = False

        return metadata

    except Exception as e:
        logger.error(f"Failed to get metadata from AI: {e}")
        metadata = _fallback_extract(user_message)
        if is_exact:
            metadata["fuzzy"] = False
        return metadata
    
    # Fallback to satisfy Pyre's path analysis of async with blocks
    metadata = _fallback_extract(user_message)
    if is_exact:
        metadata["fuzzy"] = False
    return metadata

