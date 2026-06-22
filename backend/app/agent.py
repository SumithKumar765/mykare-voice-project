import sys
import os
import json
import asyncio
import logging
import aiohttp
import sys
import os
import json
import asyncio
import logging
import aiohttp
from fastapi import FastAPI  # <-- Make sure this is here
import uvicorn               # <-- Make sure this is here

# ... your existing livekit and database imports ...

# FORCE WINDOWS TO USE SELECTOR EVENT LOOP
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- SILENCE LOGS ---
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("livekit.plugins.deepgram").setLevel(logging.CRITICAL)

from livekit.agents import JobContext, llm, WorkerOptions, cli
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import deepgram, cartesia, openai, silero
from app.db import (
    identify_user_db, fetch_slots_db, book_appointment_db,
    retrieve_appointments_db, cancel_appointment_db, modify_appointment_db
)

class ClinicAssistant(llm.FunctionContext):
    def __init__(self, room):
        super().__init__()
        self.room = room

    async def broadcast_ui_status(self, state: str, message: str):
        try:
            payload = json.dumps({"status": state, "msg": message})
            await self.room.local_participant.publish_data(payload)
        except Exception:
            pass

    @llm.ai_callable(description="Resolves user ID by matching phone numbers.")
    async def identify_user(self, name: str, phone_number: str):
        await self.broadcast_ui_status("pending", f"Identifying {name}...")
        result = await identify_user_db(phone_number, name)
        await self.broadcast_ui_status("success", "User profile identified ✅")
        return f"User {name} identified successfully."

    @llm.ai_callable(description="Returns open booking availabilities.")
    async def fetch_slots(self, date: str = None):
        await self.broadcast_ui_status("pending", "Fetching slots...")
        result = await fetch_slots_db(date)
        slots = ", ".join(result.get("slots", []))
        await self.broadcast_ui_status("success", "Slots found ✅")
        return f"Available times are: {slots}"

    @llm.ai_callable(description="Saves appointment reservation.")
    async def book_appointment(self, user_id: str, date: str, time: str):
        await self.broadcast_ui_status("pending", "Booking...")
        result = await book_appointment_db(user_id, date, time)
        if result.get("status") == "conflict":
            return "That slot is already taken. Please ask for another time."
        await self.broadcast_ui_status("success", "Booked ✅")
        return f"Appointment confirmed for {date} at {time}."

    @llm.ai_callable(description="Retrieves a list of appointments.")
    async def retrieve_appointments(self, user_id: str):
        result = await retrieve_appointments_db(user_id, "upcoming")
        return f"Your upcoming appointments are: {str(result.get('appointments', 'none'))}"

    @llm.ai_callable(description="Cancels an appointment.")
    async def cancel_appointment(self, appointment_id: str):
        result = await cancel_appointment_db(appointment_id)
        return "Appointment has been cancelled successfully."

    @llm.ai_callable(description="Modifies an appointment.")
    async def modify_appointment(self, appointment_id: str, new_date: str, new_time: str):
        result = await modify_appointment_db(appointment_id, new_date, new_time)
        return f"Appointment successfully rescheduled to {new_date} at {new_time}."

# --- AVATAR INTEGRATION ---
async def invite_avatar_to_room(room_name: str):
    simli_api_url = "https://api.simli.ai/startAudioToVideoSession" 
    headers = {"Content-Type": "application/json"}
    
    from livekit import api
    avatar_token = api.AccessToken(os.getenv("LIVEKIT_API_KEY"), os.getenv("LIVEKIT_API_SECRET"))
    grant = api.VideoGrants(room=room_name, room_join=True, can_publish=True, can_subscribe=True)
    avatar_token.with_identity("Simli_Avatar").with_name("Receptionist").with_grants(grant)
    
    payload = {
        "apiKey": os.getenv("SIMLI_API_KEY", ""),
        "faceId": "dd10cb5a-d31d-4f12-b69f-6db3383c006e", 
        "isLivekit": True,
        "syncAudio": True,
        "livekitUrl": os.getenv("LIVEKIT_URL"),
        "livekitToken": avatar_token.to_jwt()
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(simli_api_url, json=payload, headers=headers) as response:
                if response.status in [200, 201]:
                    print("✅ Avatar joined the room!")
    except Exception as e:
        print(f"❌ Simli API Error: {e}")

async def entrypoint(ctx: JobContext):
    try:
        await ctx.connect()
        print(f"✅ Connected to: {ctx.room.name}")

        fnc_ctx = ClinicAssistant(ctx.room)
        primary_llm = openai.LLM(base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"), model="llama-3.3-70b-versatile")
        
        agent = VoicePipelineAgent(
            vad=silero.VAD.load(min_silence_duration=0.6),  
            stt=deepgram.STT(),
            llm=primary_llm,
            tts=cartesia.TTS(voice="65209f8e-6140-4a20-b819-3cc2e21da19b"),
            fnc_ctx=fnc_ctx,
            max_nested_fnc_calls=3, 
            chat_ctx=llm.ChatContext().append(
                role="system",
                text=(
                    "You are a polite Mykare Clinic receptionist. "
                    "Rule 1: Always ask for the caller's name FIRST. "
                    "Rule 2: Ask for their phone number. When provided, repeat it digit-by-digit for confirmation. "
                    "Rule 3 (STRICT): Perform all tool actions SILENTLY in the background. "
                    "Rule 4 (STRICT): Speak only natural language confirmations to the user. Never read JSON, IDs, or timestamps aloud."
                )
            )
        )

        agent.start(ctx.room)
        
        if os.getenv("SIMLI_API_KEY"):
            asyncio.create_task(invite_avatar_to_room(ctx.room.name))
        
        await agent.say("Hi, this is the Mykare Clinic assistant. Who do I have the pleasure of speaking with today?", allow_interruptions=True)

        disconnect_event = asyncio.Event()
        ctx.room.on("disconnected", lambda *args: disconnect_event.set())
        
        await disconnect_event.wait()

    except Exception as e:
        print(f"❌ Session Error: {e}")
    finally:
        print("🏁 Call closed. Worker ready for next call.")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

# --- DUMMY HTTP SERVER FOR RENDER FREE TIER & CRON-JOB ---
dummy_app = FastAPI()

@dummy_app.get("/")
def health_check():
    return {"status": "agent_worker_active"}

def run_http_server():
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(dummy_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    import threading
    # Start the dummy HTTP server in a side thread to satisfy Render's port binding requirement
    threading.Thread(target=run_http_server, daemon=True).start()
    
    # Safely clear out any extra arguments and pass 'start' to the LiveKit CLI wrapper
    sys.argv = [sys.argv[0], "start"]
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))