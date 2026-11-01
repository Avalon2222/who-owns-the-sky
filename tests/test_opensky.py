"""Tes modul opensky: header otorisasi opsional dan jalur anonim."""
from __future__ import annotations

import pytest

from src import opensky


class _Respons:
    def __init__(self, status: int, data: dict):
        self.status_code = status
        self._data = data
        self.headers = {}

    def json(self):
        return self._data


class _Sesi:
    """Sesi palsu yang mencatat argumen get/post."""

    def __init__(self, token_status: int = 200):
        self.token_status = token_status
        self.get_kwargs: dict = {}
        self.post_dipanggil = 0

    def post(self, url, data=None, timeout=None):
        self.post_dipanggil += 1
        return _Respons(self.token_status, {"access_token": "tok123", "expires_in": 1800})

    def get(self, url, params=None, timeout=None, **kwargs):
        self.get_kwargs = kwargs
        return _Respons(200, {"time": 1700000000, "states": []})


@pytest.fixture(autouse=True)
def _bersihkan(monkeypatch):
    monkeypatch.delenv("OPENSKY_CLIENT_ID", raising=False)
    monkeypatch.delenv("OPENSKY_CLIENT_SECRET", raising=False)
    opensky._TOKEN.clear()
    yield
    opensky._TOKEN.clear()


def test_tanpa_kredensial_anonim():
    sesi = _Sesi()
    data = opensky.ambil_states(session=sesi)
    assert data["states"] == []
    assert "headers" not in sesi.get_kwargs
    assert sesi.post_dipanggil == 0


def test_dengan_kredensial_memakai_bearer(monkeypatch):
    monkeypatch.setenv("OPENSKY_CLIENT_ID", "abc")
    monkeypatch.setenv("OPENSKY_CLIENT_SECRET", "rahasia")
    sesi = _Sesi()
    opensky.ambil_states(session=sesi)
    assert sesi.get_kwargs["headers"] == {"Authorization": "Bearer tok123"}
    # token disimpan: panggilan kedua tidak meminta token lagi
    opensky.ambil_states(session=sesi)
    assert sesi.post_dipanggil == 1


def test_token_gagal_tetap_anonim(monkeypatch):
    monkeypatch.setenv("OPENSKY_CLIENT_ID", "abc")
    monkeypatch.setenv("OPENSKY_CLIENT_SECRET", "salah")
    sesi = _Sesi(token_status=401)
    opensky.ambil_states(session=sesi)
    assert "headers" not in sesi.get_kwargs
