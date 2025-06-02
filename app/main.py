from fastapi import FastAPI
import motor.motor_asyncio

app = FastAPI()

client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://mongo:27017")
db = client["test_db"]

@app.get("/")
async def read_root():
    return {"message": "Hello from FastAPI with MongoDB async!"}

@app.get("/items")
async def get_items():
    items_cursor = db.items.find({}, {"_id": 0})
    items = await items_cursor.to_list(length=100)
    return {"items": items}