import os
from sentence_transformers import SentenceTransformer

cache = os.getenv("HF_HOME", "/app/models")
print("Vérification du modèle BGE-M3...")
SentenceTransformer("BAAI/bge-m3", cache_folder=cache)
print("Modèle prêt.")
