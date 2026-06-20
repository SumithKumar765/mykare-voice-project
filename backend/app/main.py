from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

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
# Pydantic validates incoming data automatically before it hits your DB
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

# Health Check Route
@app.get("/")
async def root():
    return {"status": "ok", "message": "Mykare Backend is Live!"}