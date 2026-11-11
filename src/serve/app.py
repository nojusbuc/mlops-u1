from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from serve.model_loader import load_champion

import pandas as pd


model = None
model_info = {}

@asynccontextmanager
async def lifespan(app):
    global model, model_info
    model, model_info = load_champion()
    yield

app = FastAPI(lifespan=lifespan)

class PredictRequest(BaseModel):
    texts: list[str]

@app.get("/health")
def health():
    return {"status": "ok", **model_info}

@app.post("/predict")
def predict(request: PredictRequest):
    if len(request.texts) == 0:
        raise HTTPException(status_code=400, detail="texts is empty")
    predictions = model.predict(pd.DataFrame({"text": request.texts}))
    return {"predictions": [int(p) for p in predictions], "model_version": model_info["version"]}