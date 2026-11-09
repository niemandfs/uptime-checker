from datetime import datetime, timezone

import httpx
from fastapi import FastAPI

app = FastAPI(title="Uptime Checker")

SITES = [
    "https://example.com",
    "https://github.com",
    "https://www.cloudflare.com",
]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
async def status():
    results = []
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        for url in SITES:
            try:
                r = await client.get(url)
                results.append({
                    "url": url,
                    "up": r.status_code < 400,
                    "status_code": r.status_code,
                    "response_ms": round(r.elapsed.total_seconds() * 1000),
                })
            except httpx.RequestError as e:
                results.append({
                    "url": url,
                    "up": False,
                    "status_code": None,
                    "error": type(e).__name__,
                })
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
