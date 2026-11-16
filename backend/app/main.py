import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
import psycopg
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# Alamat database, diambil dari environment (diisi docker-compose dari .env)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Daftar website yang dicek
SITES = [
    "https://example.com",
    "https://github.com",
    "https://www.cloudflare.com",
]

# Perintah SQL buat bikin tabel "checks" kalau belum ada
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS checks (
    id SERIAL PRIMARY KEY,
    checked_at TIMESTAMPTZ NOT NULL,
    url TEXT NOT NULL,
    up BOOLEAN NOT NULL,
    status_code INTEGER,
    response_ms INTEGER,
    error TEXT
)
"""


# Jalan sekali waktu aplikasi start: bikin tabel di database
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        await conn.execute(CREATE_TABLE)
    yield


app = FastAPI(title="Uptime Checker", lifespan=lifespan)

# CORS: izinkan website lain (frontend di Cloudflare Pages) baca data dari API ini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
)


# Cek apakah API-nya hidup
@app.get("/health")
def health():
    return {"status": "ok"}


# Cek semua website, simpan hasilnya ke database, lalu kirim hasilnya
@app.get("/status")
async def status():
    results = []

    # Kirim request ke tiap website dan catat hasilnya
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        for url in SITES:
            try:
                r = await client.get(url)
                results.append({
                    "url": url,
                    "up": r.status_code < 400,  # Kode di bawah 400 dianggap UP
                    "status_code": r.status_code,
                    "response_ms": round(r.elapsed.total_seconds() * 1000),
                })
            except httpx.RequestError as e:
                # Website nggak bisa dihubungi (timeout, DNS error, dll)
                results.append({
                    "url": url,
                    "up": False,
                    "status_code": None,
                    "error": type(e).__name__,
                })

    checked_at = datetime.now(timezone.utc)

    # Simpan semua hasil cek ke tabel "checks"
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO checks (checked_at, url, up, status_code, response_ms, error) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    (checked_at, r["url"], r["up"], r.get("status_code"),
                     r.get("response_ms"), r.get("error"))
                    for r in results
                ],
            )

    return {
        "checked_at": checked_at.isoformat(),
        "results": results,
    }


# Ambil riwayat hasil cek dari database (paling baru di atas)
# limit = jumlah data yang diambil, dibatasi 1 sampai 500
@app.get("/history")
async def history(limit: int = Query(50, ge=1, le=500)):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT checked_at, url, up, status_code, response_ms, error "
                "FROM checks ORDER BY checked_at DESC, id DESC LIMIT %s",
                (limit,),
            )
            rows = await cur.fetchall()

    # Ubah data dari database jadi format JSON
    return {
        "results": [
            {
                "checked_at": row[0].isoformat(),
                "url": row[1],
                "up": row[2],
                "status_code": row[3],
                "response_ms": row[4],
                "error": row[5],
            }
            for row in rows
        ]
    }