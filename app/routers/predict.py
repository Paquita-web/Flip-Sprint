from fastapi import APIRouter
from schemas.input_data import InputData
from schemas.prediction_output import PredictionOutput

router = APIRouter()

@router.post("/predict", response_model=PredictionOutput, tags=["inference"])
def make_prediction(data: InputData):
    # Ejemplo simple: suma ponderada simulando inferencia
    score = (data.feature_1 * 0.3) + (data.feature_2 * 0.7)
    label = "Clase A" if score > 0 else "Clase B"
    return PredictionOutput(prediction=score, label=label, confidence=abs(score))
