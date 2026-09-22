from pathlib import Path
import joblib
import numpy as np

from sentence_transformers import SentenceTransformer

class QueryRouter:
    MODEL_NAME = (
        "sentence-transformers/"
        "paraphrase-multilingual-MiniLM-L12-v2"
    )

    def __init__(self, threshold: float=0.6,):
        self.threshold=threshold
        self.embedding_model=(SentenceTransformer(self.MODEL_NAME))

        model_path=(Path(__file__).resolve().parent/"model"/"query_router.joblib")
        if not model_path.exists():
            raise FileNotFoundError(f"Router model not found: {model_path}")
        self.classifier=joblib.load(model_path)

    def route(self,query:str, )->dict:
        if not query or not query.strip():
            raise ValueError("Query cannot empty")
        vector=self.embedding_model.encode([query],normalize_embeddings=True,
                                           convert_to_numpy=True, show_progress_bar=False, )
        vector=np.asarray(vector, dtype=np.float32)

        probabilities=(self.classifier.predict_proba(vector)[0])
        classes=(self.classifier.classes_)

        best_index=int(np.argmax(probabilities))
        label=classes[best_index]
        confidence=float(probabilities[best_index])

        if confidence < self.threshold:
            label= "RETRIEVE"

        return {
            "route": label,
            "confidence": confidence,
        }

        
