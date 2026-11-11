from fastapi.testclient import TestClient

from serve import app as serve_app


class FakeModel:
    def predict(self, df):
        return [1] * len(df)


def fake_load_champion():
    return FakeModel(), {"name": "imdb-sentiment", "alias": "champion", "version": "7", "run_id": "abc"}


def test_health(monkeypatch):
    monkeypatch.setattr(serve_app, "load_champion", fake_load_champion)
    with TestClient(serve_app.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == "7"


def test_predict(monkeypatch):
    monkeypatch.setattr(serve_app, "load_champion", fake_load_champion)
    with TestClient(serve_app.app) as client:
        response = client.post("/predict", json={"texts": ["good", "bad"]})
    assert response.status_code == 200
    assert response.json()["predictions"] == [1, 1]


def test_predict_empty(monkeypatch):
    monkeypatch.setattr(serve_app, "load_champion", fake_load_champion)
    with TestClient(serve_app.app) as client:
        response = client.post("/predict", json={"texts": []})
    assert response.status_code == 400
