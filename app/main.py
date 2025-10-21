from fastapi import FastAPI
from app.routers import health, predict

app = FastAPI(title="ML Prediction API", version="0.1.0")

# Endpoint raíz
@app.get("/")
def root():
    return {"status": "ok", "service": "ML-Prediction-API"}

# Incluir routers
app.include_router(health.router)
app.include_router(predict.router)
