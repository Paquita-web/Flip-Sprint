from pydantic import BaseModel

class PredictionOutput(BaseModel):
    prediction: float
    label: str
    confidence: float
