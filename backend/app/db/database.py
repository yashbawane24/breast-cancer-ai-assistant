from motor.motor_asyncio import AsyncIOMotorClient
from urllib.parse import urlparse
from app.config import settings

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

db = MongoDB()

async def connect_to_mongo():
    parsed = urlparse(settings.mongo_uri)
    db_name = parsed.path.lstrip('/')
    if not db_name:
        db_name = "healthcare_assistant"
    db.client = AsyncIOMotorClient(settings.mongo_uri)
    db.db = db.client[db_name]
    print(f"Connected to MongoDB (db: {db_name})")

async def close_mongo_connection():
    if db.client:
        db.client.close()
        print("Closed MongoDB connection")
