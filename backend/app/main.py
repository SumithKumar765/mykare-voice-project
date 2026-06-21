import sys
import asyncio

# FORCE WINDOWS TO USE SELECTOR EVENT LOOP (Prevents WinError 10054 Connection Resets)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from livekit import api
from dotenv import load_dotenv

# Actually load the .env variables into the OS
load_dotenv() 

from app.db import (
    identify_user_db,
    fetch_slots_db,
    book_appointment_db,
    retrieve_appointments_db,
    cancel_appointment_db,
    modify_appointment_db
)

app = FastAPI(title="Mykare Voice Agent API")

# Setup CORS to allow your Vite frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Request Data Models ---
class IdentifyUserReq(BaseModel):
    phone_number: str
    name: Optional[str] = None

class BookAppointmentReq(BaseModel):
    user_id: str
    date: str
    time: str

class ModifyAppointmentReq(BaseModel):
    new_date: str
    new_time: str

# --- Core API Endpoints ---
@app.post("/users/identify")
async def identify_user(req: IdentifyUserReq):
    return await identify_user_db(req.phone_number, req.name)

@app.get("/slots")
async def get_slots(date: Optional[str] = None):
    return await fetch_slots_db(date)

@app.post("/appointments")
async def book_appointment(req: BookAppointmentReq):
    return await book_appointment_db(req.user_id, req.date, req.time)

@app.get("/appointments")
async def get_appointments(user_id: str, status: str = "confirmed"):
    return await retrieve_appointments_db(user_id, status)

@app.patch("/appointments/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: str):
    return await cancel_appointment_db(appointment_id)

@app.patch("/appointments/{appointment_id}")
async def modify_appointment(appointment_id: str, req: ModifyAppointmentReq):
    return await modify_appointment_db(appointment_id, req.new_date, req.new_time)

# --- LiveKit Token Generation ---
@app.get("/get-token") 
async def get_token(room_name: str = "mykare-clinic-room", participant_name: str = "Caller"):
    """Generates a secure WebRTC token for the frontend to connect."""
    token = api.AccessToken(
        os.getenv("LIVEKIT_API_KEY"), 
        os.getenv("LIVEKIT_API_SECRET")
    )
    
    grant = api.VideoGrants(room=room_name, room_join=True)
    token.with_identity(participant_name).with_name(participant_name).with_grants(grant)
    
    return {"token": token.to_jwt()}

@app.get("/")
async def root():
    return {"status": "ok", "message": "Mykare Backend is Live!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)