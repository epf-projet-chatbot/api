FROM python:3.11

WORKDIR /app

COPY app/requirements.txt .

# Copie le code RAG dans /app/rag
COPY ../rag ./rag

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install -e ./rag

COPY app/ .

ENV PYTHONPATH=/app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]