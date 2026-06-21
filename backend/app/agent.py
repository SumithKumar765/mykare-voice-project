import os
import json
import asyncio
import logging

# Silence the noisy background network logs
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
        """Sends live status updates directly to the frontend UI panel."""
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

async def entrypoint(ctx: JobContext):
    """The main entrypoint that runs when a user connects via the frontend."""
    await ctx.connect()
    print(f"🔗 Connected to WebRTC Room: {ctx.room.name}")

    fnc_ctx = ClinicAssistant(ctx.room)

    # 1. Primary Model (Smartest)
    primary_llm = openai.LLM(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile" 
    )
    
    # 2. First Fallback (Fastest, Actively Supported)
    backup_llm_1 = openai.LLM(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.1-8b-instant" 
    )

    # 3. Second Fallback (Reliable Backup, Actively Supported)
    backup_llm_2 = openai.LLM(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
        model="gemma2-9b-it" 
    )

    # Build the real-time AI pipeline 
    agent = VoicePipelineAgent(
        vad=silero.VAD.load(min_silence_duration=0.5),  # Adjust VAD sensitivity for natural conversation flow
        stt=deepgram.STT(),
        # Seamlessly hot-swap the LLMs if a limit or error is hit
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

    agent.start(ctx.room)
    await agent.say("Hi, this is the Mykare Clinic assistant. Who do I have the pleasure of speaking with today?", allow_interruptions=True)

    # Safely wait for the user to disconnect without crashing
    disconnect_event = asyncio.Event()
    ctx.room.on("disconnected", lambda: disconnect_event.set())
    await disconnect_event.wait()
        
    print("👋 User disconnected. Ready to trigger call log summary generation.")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))