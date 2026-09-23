from pathlib import Path
import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression

from BackEnd.app.query_router.dataset import (DIRECT_QUERIES, RETRIEVE_QUERIES,)

model = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

texts=(DIRECT_QUERIES+RETRIEVE_QUERIES)

labels=(["DIRECTS"]*len(DIRECT_QUERIES)+["RETRIEVE"]*len(RETRIEVE_QUERIES))

embedding_model=SentenceTransformer(model)

vectors=embedding_model.encode(
    texts, normalize_embeddings=True, 
    convert_to_numpy=True,
    show_progress_bar=True,
)

vectors=np.asarray(vectors, dtype=np.float32,)
classifier=LogisticRegression(
    max_iter=1000,
    random_state=42,
)

classifier.fit(vectors, labels)

train_accuracy = classifier.score(vectors, labels)

print("Training accuracy:", train_accuracy)
print("Classes:", classifier.classes_)

model_dir=(Path(__file__).resolve().parent/"model")
model_dir.mkdir(
    parents=True, exist_ok=True,
)
model_path=(model_dir/"query_router.joblib")
joblib.dump(classifier,model_path,)