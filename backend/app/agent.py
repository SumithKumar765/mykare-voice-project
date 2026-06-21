import sys
import os
import json
import asyncio
import logging
import aiohttp

# FORCE WINDOWS TO USE SELECTOR EVENT LOOP (Prevents WinError 10054 Connection Resets)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Silence noisy background network logs
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

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
        payload = json.dumps({"status": state, "msg": message})
        await self.room.local_participant.publish_data(payload)

    @llm.ai_callable(description="Resolves user ID by matching phone numbers. Must have both name and phone number to call.")
    async def identify_user(self, name: str, phone_number: str):
        await self.broadcast_ui_status("pending", f"Looking up profile for {phone_number}...")
        result = await identify_user_db(phone_number, name)
        await self.broadcast_ui_status("success", "User profile identified ✅")
        return json.dumps(result)

    @llm.ai_callable(description="Returns open booking availabilities for a date.")
    async def fetch_slots(self, date: str = None):
        await self.broadcast_ui_status("pending", "Fetching available slots...")
        result = await fetch_slots_db(date)
        await self.broadcast_ui_status("success", f"Found {len(result['slots'])} slots ✅")
        return json.dumps(result)

    @llm.ai_callable(description="Saves appointment reservation into database.")
    async def book_appointment(self, user_id: str, date: str, time: str):
        await self.broadcast_ui_status("pending", "Securing appointment slot...")
        result = await book_appointment_db(user_id, date, time)
        if result.get("status") == "conflict":
            await self.broadcast_ui_status("conflict", "Slot taken! Re-checking...")
        else:
            await self.broadcast_ui_status("success", f"Booking confirmed for {date} at {time} ✅")
        return json.dumps(result)

    @llm.ai_callable(description="Retrieves a list of the user's existing or upcoming appointments.")
    async def retrieve_appointments(self, user_id: str, status_filter: str = "upcoming"):
        await self.broadcast_ui_status("pending", "Retrieving appointment history...")
        result = await retrieve_appointments_db(user_id, status_filter)
        await self.broadcast_ui_status("success", "Appointments retrieved ✅")
        return json.dumps(result)

    @llm.ai_callable(description="Cancels an existing appointment using its appointment ID.")
    async def cancel_appointment(self, appointment_id: str):
        await self.broadcast_ui_status("pending", "Processing cancellation request...")
        result = await cancel_appointment_db(appointment_id)
        if result.get("status") in ["not_found", "already_cancelled"]:
            await self.broadcast_ui_status("conflict", "Could not cancel appointment.")
        else:
            await self.broadcast_ui_status("success", "Appointment cancelled successfully ✅")
        return json.dumps(result)

    @llm.ai_callable(description="Modifies the date and time of an existing appointment.")
    async def modify_appointment(self, appointment_id: str, new_date: str, new_time: str):
        await self.broadcast_ui_status("pending", "Rescheduling appointment...")
        result = await modify_appointment_db(appointment_id, new_date, new_time)
        if result.get("status") == "conflict":
            await self.broadcast_ui_status("conflict", "New time slot is unavailable.")
        elif result.get("status") == "not_found":
            await self.broadcast_ui_status("conflict", "Appointment not found.")
        else:
            await self.broadcast_ui_status("success", f"Rescheduled to {new_date} at {new_time} ✅")
        return json.dumps(result)

# --- AVATAR INTEGRATION (SIMLI) ---
async def invite_avatar_to_room(room_name: str):
    """Triggers the Simli visual avatar to join your LiveKit room."""
    print("🤖 Inviting Visual Avatar to the room via Simli...")
    
    simli_api_url = "https://api.simli.ai/startAudioToVideoSession" 
    
    headers = {
        "Content-Type": "application/json"
    }
    
    from livekit import api
    avatar_token = api.AccessToken(os.getenv("LIVEKIT_API_KEY"), os.getenv("LIVEKIT_API_SECRET"))
    grant = api.VideoGrants(room=room_name, room_join=True, can_publish=True, can_subscribe=True)
    avatar_token.with_identity("Simli_Avatar").with_name("Receptionist").with_grants(grant)
    
    # Payload matching Simli API expectations (apiKey inside the body)
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
                    print("✅ Avatar successfully triggered and is joining the room!")
                else:
                    error_data = await response.text()
                    print(f"⚠️ Avatar API returned an error: {error_data}")
    except Exception as e:
        print(f"❌ Failed to reach Avatar API: {e}")

async def entrypoint(ctx: JobContext):
    """Main execution loop triggered when the user connects from the frontend."""
    try:
        # Connection retry loop
        while True:
            try:
                print("🔗 Connecting to LiveKit server room...")
                await ctx.connect()
                print(f"✅ Connected to WebRTC Room: {ctx.room.name}")
                break
            except Exception as conn_err:
                print(f"⚠️ Connection failed: {conn_err}. Retrying in 2 seconds...")
                await asyncio.sleep(2)

        fnc_ctx = ClinicAssistant(ctx.room)

        primary_llm = openai.LLM(base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"), model="llama-3.3-70b-versatile")
        backup_llm_1 = openai.LLM(base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"), model="llama-3.1-8b-instant")
        backup_llm_2 = openai.LLM(base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"), model="gemma2-9b-it")

        print("📡 Initializing audio pipeline components...")
        print(f"🎤 STT: Deepgram (API key: {'✓' if os.getenv('DEEPGRAM_API_KEY') else '✗'})")
        print(f"🔊 TTS: Cartesia (API key: {'✓' if os.getenv('CARTESIA_API_KEY') else '✗'})")

        agent = VoicePipelineAgent(
            vad=silero.VAD.load(min_silence_duration=0.5),  
            stt=deepgram.STT(),
            llm=llm.FallbackAdapter([primary_llm, backup_llm_1, backup_llm_2]),
            tts=cartesia.TTS(voice="65209f8e-6140-4a20-b819-3cc2e21da19b"),
            fnc_ctx=fnc_ctx,
            chat_ctx=llm.ChatContext().append(
                role="system",
                text=(
                    "You are a polite, efficient healthcare receptionist at Mykare Clinic. "
                    "Keep responses brief and highly conversational (1-2 sentences maximum). "
                    "Rule 1: Always ask for the caller's name FIRST. "
                    "Rule 2: Once they provide their name, acknowledge it and then ask for their phone number. Do not ask for both at the same time. "
                    "Rule 3: Always confirm phone numbers digit-by-digit before executing the identify_user tool. "
                    "CRITICAL RULE 1: NEVER speak raw JSON, markdown, or <function> tags aloud. When you need to use a tool, execute it silently without narrating the code. "
                    "CRITICAL RULE 2: NEVER speak database UUIDs, appointment IDs, or user IDs aloud to the caller. Simply confirm the action naturally."
                )
            )
        )

        print("🎙️ Starting voice agent...")
        agent.start(ctx.room)
        print("✅ Agent started successfully!")
        
        # Trigger Simli Avatar if key exists in .env
        if os.getenv("SIMLI_API_KEY"):
            asyncio.create_task(invite_avatar_to_room(ctx.room.name))
        else:
            print("⚠️ SIMLI_API_KEY not found in .env. Skipping avatar invitation.")
        
        await agent.say("Hi, this is the Mykare Clinic assistant. Who do I have the pleasure of speaking with today?", allow_interruptions=True)
        print("🎵 Initial greeting sent!")

        disconnect_event = asyncio.Event()
        ctx.room.on("disconnected", lambda: disconnect_event.set())
        await disconnect_event.wait()
            
        print("👋 User disconnected. Call log session finished.")
    
    except Exception as e:
        print(f"❌ CRITICAL ERROR in entrypoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))