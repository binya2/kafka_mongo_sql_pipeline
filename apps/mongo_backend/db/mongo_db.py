"""
MongoDB Database Connection and Initialization
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

# Import all document models
from shared.models.user import User
from shared.models.supplier import Supplier
from shared.models.product import Product
from shared.models.order import Order
from shared.models.post import Post


# MongoDB connection settings (from environment variables)
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "social_commerce")


async def init_db():
    """Initialize database connection and Beanie ODM"""
    # Create MongoDB client
    client = AsyncIOMotorClient(MONGODB_URL)

    # Initialize Beanie with all document models
    await init_beanie(
        database=client[DATABASE_NAME],
        document_models=[
            User,
            Supplier,
            Product,
            Order,
            Post,
        ]
    )

    print(f"✓ Connected to MongoDB: {DATABASE_NAME}")
    print("✓ Initialized Beanie ODM with all models")
