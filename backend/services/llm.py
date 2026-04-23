import os
import json
import re
import logging
# pyre-ignore[21]
import httpx
from typing import Dict, Any

logger = logging.getLogger(__name__)

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
                substr: str = text[start:end+1]  # type: ignore
                return json.loads(substr)
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from response")

async def extract_metadata_from_query(user_message: str, groq_api_key: str) -> Dict[str, Any]:
    """
    Uses the LLM to extract structured metadata from the user's query.
    """
    if not groq_api_key or groq_api_key == "your_groq_api_key_here":
        # Fallback dummy metadata
        return {
            "title": user_message,
            "author": "",
            "year": "",
            "format": "pdf",
            "fuzzy": True
        }

    system_prompt = """You are a precise Book Metadata Extraction Agent.
Your job is to analyze a user's request for a book and extract structured metadata.

Extract the following fields:
- title: The title of the book.
- author: The author of the book (if mentioned).
- year: The publication year (if mentioned).
- format: The preferred file format ('pdf', 'epub', or 'any'). Defaults to 'pdf' if unclear.
- fuzzy: true or false. Set to true if the query is ambiguous, missing an author, has a partial title, or is a vague description. Set to false if it's a very specific, exact request with title and author.

OUTPUT FORMAT:
You must output ONLY valid JSON in this exact structure:
{
  "title": "Exact Book Title",
  "author": "Author Name",
  "year": "1984",
  "format": "pdf",
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
        async with httpx.AsyncClient(timeout=60.0) as client:
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
                metadata["format"] = "pdf"
            if "fuzzy" not in metadata:
                metadata["fuzzy"] = True

            return metadata

    except Exception as e:
        logger.error(f"Failed to get metadata from AI: {e}")
        return {
            "title": user_message,
            "author": "",
            "year": "",
            "format": "pdf",
            "fuzzy": True
        }
    
    # Fallback to satisfy Pyre's path analysis of async with blocks
    return {
        "title": user_message,
        "author": "",
        "year": "",
        "format": "pdf",
        "fuzzy": True
    }

