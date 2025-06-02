from fastapi import FastAPI
from pymongo import MongoClient

app = FastAPI()

client = MongoClient("mongodb://mongo:27017")
db = client["test_db"]

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI with MongoDB!"}

@app.get("/items")
def get_items():
    items = list(db.items.find({}, {"_id": 0}))
    return {"items": items}