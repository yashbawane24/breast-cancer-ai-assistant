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
    
    # Configure high-performance connection pooling
    db.client = AsyncIOMotorClient(
        settings.mongo_uri,
        maxPoolSize=50,
        minPoolSize=5,
        maxIdleTimeMS=45000,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000
    )
    db.db = db.client[db_name]
    
    # Create critical database indexes for instant lookups
    try:
        await db.db.users.create_index("email", unique=True, background=True)
        await db.db.reports.create_index([("patient_id", 1), ("upload_date", -1)], background=True)
        await db.db.reports.create_index([("patient_id", 1), ("status", 1)], background=True)
        print(f"Connected to MongoDB (db: {db_name}) with high-speed indexes active.")
    except Exception as idx_err:
        print(f"Note on MongoDB index creation: {idx_err}")

async def close_mongo_connection():
    if db.client:
        db.client.close()
        print("Closed MongoDB connection")
