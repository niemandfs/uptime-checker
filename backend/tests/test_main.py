from fastapi.testclient import TestClient

from app.main import app

# "Browser palsu" buat nyobain API tanpa harus nyalain server.
# Sengaja nggak pakai "with", jadi aplikasi nggak nyambung ke database waktu test.
client = TestClient(app)


# Cek /health jawab dengan status ok
def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# Cek /history nolak limit yang terlalu kecil (minimal 1)
def test_history_limit_too_small():
    response = client.get("/history?limit=0")
    assert response.status_code == 422


# Cek /history nolak limit yang terlalu besar (maksimal 500)
def test_history_limit_too_big():
    response = client.get("/history?limit=501")
    assert response.status_code == 422