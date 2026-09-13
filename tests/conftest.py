"""Aísla el estado local de cada prueba de interfaz."""

import pytest


@pytest.fixture(autouse=True)
def _localappdata_aislado(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
