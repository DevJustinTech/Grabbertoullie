# pyre-ignore-all-errors - triggered reload
from fastapi import FastAPI, Request, HTTPException, Response  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import StreamingResponse # type: ignore
from services.llm import extract_metadata_from_query
from services.pipeline import perform_parallel_search, score_and_rank_results, format_best_result, needs_disambiguation, generate_disambiguation_payload, validate_url  # pyre-ignore
from annas_archive import resolve_slow_download

import asyncio
import socket
import ipaddress
from pydantic import BaseModel  # type: ignore
import httpx  # type: ignore
import os
import json
import logging
from typing import Tuple
from urllib.parse import urlparse
from dotenv import load_dotenv  # type: ignore

# explicitly load the .env from the backend/ directory so it is found regardless of cwd
backend_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(backend_dir, ".env"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3001").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class ChatRequest(BaseModel):
    message: str

async def chat_stream_generator(user_message: str):
    """Generates SSE events for the chat endpoint."""

    # We yield directly from the main generator function
    # so we don't nest generators improperly.

    try:
        # Step 1: Extract Metadata
        yield f"data: {json.dumps({'type': 'status', 'message': 'Understanding your request...'})}\n\n"
        await asyncio.sleep(0.05)
        metadata = await extract_metadata_from_query(user_message, GROQ_API_KEY)

        # Step 2: Parallel Search
        sources_str = "Anna's Archive, Z-Library, Open Library, Gutenberg, and Standard Ebooks"
        yield f"data: {json.dumps({'type': 'status', 'message': f'Searching {sources_str}...'})}\n\n"
        await asyncio.sleep(0.05)
        results = await perform_parallel_search(metadata)

        if not results:
            yield f"data: {json.dumps({'type': 'status', 'message': 'No results found across any sources.'})}\n\n"
            await asyncio.sleep(0.05)
            final = {"type": "result", "data": {"status": "fail", "reason": "No results found from any search source."}}
            yield f"data: {json.dumps(final)}\n\n"
            return

        yield f"data: {json.dumps({'type': 'status', 'message': f'Found {len(results)} potential matches. Scoring and ranking...'})}\n\n"
        await asyncio.sleep(0.05)

        # Step 3: Score and Rank
        ranked = score_and_rank_results(results, metadata)

        # Step 4: Check for Disambiguation
        if needs_disambiguation(ranked, metadata):
            payload = generate_disambiguation_payload(ranked, metadata)
            # If after deduplication we only have 1 unique candidate, skip disambiguation
            if len(payload.get("candidates", [])) > 1:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Multiple matches found. Need clarification.'})}\n\n"
                await asyncio.sleep(0.05)
                final = {"type": "disambiguation", "data": payload}
                yield f"data: {json.dumps(final)}\n\n"
                return

        # Step 5: Validate Top Results
        # Validate a generous window of candidates (not just the top few): the
        # highest-ranked links often sit behind login walls (Z-Library) or are
        # lending-only (archive.org 401), so we need to fall through to reliable
        # lower-ranked sources like Anna's Archive. Validation runs concurrently.
        MAX_CANDIDATES_TO_VALIDATE = 8
        top_candidates = [r for r in ranked if r.get("_score", 0) >= 0][:MAX_CANDIDATES_TO_VALIDATE]  # type: ignore
        if not top_candidates:
             yield f"data: {json.dumps({'type': 'status', 'message': 'Matches found, but none met the criteria.'})}\n\n"
             await asyncio.sleep(0.05)
             final = {"type": "result", "data": {"status": "fail", "reason": "Found matches, but they didn't match the requested format or quality criteria."}}
             yield f"data: {json.dumps(final)}\n\n"
             return

        yield f"data: {json.dumps({'type': 'status', 'message': 'Verifying download links...'})}\n\n"
        await asyncio.sleep(0.05)

        target_format = metadata.get("format", "pdf")

        async def validate_candidate(candidate):
            # Try to validate the preferred format link first
            if target_format == "pdf" and candidate.get("pdf_url"):
                if await validate_url(candidate["pdf_url"]):
                    return candidate, "pdf"
            elif target_format == "epub" and candidate.get("epub_url"):
                if await validate_url(candidate["epub_url"]):
                    return candidate, "epub"
            elif target_format == "any":
                if candidate.get("epub_url") and await validate_url(candidate["epub_url"]):
                    return candidate, "epub"
                if candidate.get("pdf_url") and await validate_url(candidate["pdf_url"]):
                    return candidate, "pdf"

            # Fallback to the other format if it exists and we haven't checked it
            if candidate.get("pdf_url") and target_format != "pdf" and target_format != "any":
                if await validate_url(candidate["pdf_url"]):
                    return candidate, "pdf"
            if candidate.get("epub_url") and target_format != "epub" and target_format != "any":
                if await validate_url(candidate["epub_url"]):
                    return candidate, "epub"

            return None, None

        # Validate concurrently
        validation_results = await asyncio.gather(*[validate_candidate(c) for c in top_candidates])

        best_result = None
        best_format = None
        # pyright has a bug where it fails to evaluate `await asyncio.gather(*[...])` as unwrapping Coroutines
        for candidate, fmt in validation_results:  # type: ignore
            if candidate is not None:
                best_result = candidate
                best_format = fmt
                break

        if best_result:
            yield f"data: {json.dumps({'type': 'status', 'message': 'Link verified ✓'})}\n\n"
            await asyncio.sleep(0.05)

            # Temporarily update format just for formatting if it's "any"
            temp_format = target_format
            if temp_format == "any":
                temp_format = best_format

            final_data = format_best_result(best_result, temp_format)
            logger.info(f"RESULT for '{user_message}': SUCCESS via {final_data.get('source')} -> {final_data.get('file_url')}")
            final = {"type": "result", "data": final_data}
            yield f"data: {json.dumps(final)}\n\n"
        else:
            # Explicitly fail if no direct link could be verified
            yield f"data: {json.dumps({'type': 'status', 'message': 'Could not verify any direct links.'})}\n\n"
            await asyncio.sleep(0.05)

            logger.info(f"RESULT for '{user_message}': FAIL - no direct link verified among {len(top_candidates)} candidates")
            final_data = {
                "status": "fail",
                "reason": "Could not find a direct download link for this book."
            }
            final = {"type": "result", "data": final_data}
            yield f"data: {json.dumps(final)}\n\n"

    except Exception as e:
        logger.error(f"Error in chat stream: {e}", exc_info=True)
        final = {"type": "result", "data": {"status": "fail", "reason": "An internal error occurred."}}
        yield f"data: {json.dumps(final)}\n\n"


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    return StreamingResponse(
        chat_stream_generator(request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

async def is_valid_url(url: str) -> Tuple[bool, str]:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False, "Invalid URL scheme. Only HTTP and HTTPS are allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL format."

        # Optional: Resolve hostname to IP and check if it's public.
        # This prevents accessing localhost or internal networks.
        # Use asyncio.get_running_loop().getaddrinfo to prevent blocking the event loop
        # during DNS resolution.
        try:
            # Prevent SSRF: Resolve to IP and block private/loopback/restricted IPs.
            # Use getaddrinfo to support both IPv4 and IPv6 to prevent IPv6 bypasses.
            # ⚡ Bolt: Use loop.getaddrinfo() to prevent the synchronous socket.getaddrinfo()
            # from blocking the asyncio event loop during slow DNS resolutions.
            loop = asyncio.get_running_loop()
            addr_info = await loop.getaddrinfo(hostname, None)
            for res in addr_info:
                ip = res[4][0]
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_link_local:
                    return False, "Invalid or restricted URL domain/IP."
        except socket.gaierror:
            pass  # DNS resolution failed, might still be valid or handled by httpx later

        return True, ""
    except Exception as e:
        return False, str(e)

async def check_url_hook(request: httpx.Request):
    # Prevent SSRF by validating redirects using the same is_valid_url logic
    valid, reason = await is_valid_url(str(request.url))
    if not valid:
        # Instead of ValueError, we can raise an HTTPException so it is handled correctly by FastAPI
        raise HTTPException(status_code=400, detail=f"SSRF Attempt blocked: {reason}")

@app.get("/api/download")
async def download_endpoint(url: str):
    valid, reason = await is_valid_url(url)
    if not valid:
        raise HTTPException(status_code=400, detail=reason)

    try:
        async with httpx.AsyncClient(follow_redirects=True, event_hooks={"request": [check_url_hook]}) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Use a strict allow-list for upstream headers to prevent Header Injection (e.g., Set-Cookie, XSS)
            safe_headers = {"content-type", "content-length"}
            headers: dict[str, str] = {
                k.lower(): v for k, v in response.headers.items() if k.lower() in safe_headers
            }
            if "content-type" not in headers:
                headers["content-type"] = "application/octet-stream"

            # Suggest a filename from the URL or Content-Disposition
            content_disposition = response.headers.get("content-disposition")
            if content_disposition:
                # Sanitize upstream header to prevent HTTP header injection
                sanitized_disposition = re.sub(r'[\r\n]', '', content_disposition)
                headers["content-disposition"] = sanitized_disposition
            else:
                filename = url.split("/")[-1]
                if not filename or "?" in filename:
                    filename = "downloaded_file"

                # Sanitize filename to prevent HTTP header injection and escaping quotes
                sanitized_filename = re.sub(r'[\r\n"]', '_', filename)
                headers["content-disposition"] = f'attachment; filename="{sanitized_filename}"'

            return Response(content=response.content, status_code=response.status_code, headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=400, detail="Download failed due to an internal error.")


def _is_valid_md5(value: str) -> bool:
    return len(value) == 32 and all(c in "0123456789abcdefABCDEF" for c in value)


@app.get("/api/annas-download")
async def annas_download_endpoint(md5: str):
    """
    Resolve a direct download URL for an Anna's Archive book (identified by its
    md5) by driving the slow-download flow in a real browser. This takes ~10-30s
    and requires a headed browser, so it runs on demand when the user clicks the
    download button rather than during search.
    """
    if not _is_valid_md5(md5):
        raise HTTPException(status_code=400, detail="Invalid Anna's Archive book id.")

    try:
        download_url = await resolve_slow_download(md5)
    except Exception as e:
        logger.error(f"Anna's Archive resolution error for {md5}: {e}")
        raise HTTPException(status_code=502, detail="Failed to resolve download link.")

    if not download_url:
        logger.info(f"RESOLVE for {md5}: no link (servers busy or challenge failed)")
        raise HTTPException(
            status_code=502,
            detail="Could not resolve a direct download link (all partner servers were busy or unavailable). Please try again.",
        )

    logger.info(f"RESOLVE for {md5}: SUCCESS -> {download_url}")
    return {"download_url": download_url}


if __name__ == "__main__":
    import uvicorn  # type: ignore
    uvicorn.run(app, host="0.0.0.0", port=8001)
