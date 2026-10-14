"""Authentication routes: signup, login, token refresh."""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.models.user import UserCreate, UserOut, UserInDB
from app.core.security import get_password_hash, verify_password, create_access_token, get_current_user_id
from app.db.database import db

router = APIRouter()

@router.post("/signup", response_model=UserOut)
async def signup(user: UserCreate):
    existing_user = await db.db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Run CPU-bound bcrypt in worker thread to prevent event-loop stalling
    hashed_password = await asyncio.to_thread(get_password_hash, user.password)
    user_in_db = UserInDB(**user.model_dump(), hashed_password=hashed_password)
    
    result = await db.db.users.insert_one(user_in_db.model_dump())
    
    return UserOut(
        id=str(result.inserted_id),
        **user.model_dump(),
        created_at=user_in_db.created_at
    )

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user_dict = await db.db.users.find_one({"email": form_data.username})
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    # Run CPU-bound bcrypt in worker thread to prevent event-loop stalling
    is_valid = await asyncio.to_thread(verify_password, form_data.password, user_dict["hashed_password"])
    if not is_valid:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": str(user_dict["_id"])})
    
    user_out = UserOut(
        id=str(user_dict["_id"]),
        email=user_dict["email"],
        full_name=user_dict.get("full_name", ""),
        role=user_dict.get("role", "patient"),
        created_at=user_dict.get("created_at")
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": user_out.model_dump()
    }

@router.get("/me", response_model=UserOut)
async def get_me(user_id: str = Depends(get_current_user_id)):
    from bson import ObjectId
    user_dict = await db.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_dict:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserOut(
        id=str(user_dict["_id"]),
        email=user_dict["email"],
        full_name=user_dict["full_name"],
        role=user_dict["role"],
        created_at=user_dict["created_at"]
    )
