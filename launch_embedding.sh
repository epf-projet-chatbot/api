#!/bin/bash
echo "📦 Lancement de embedding.py..."
python3 rag/embedding.py

echo "🚀 Lancement de l'API..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
