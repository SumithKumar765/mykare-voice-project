import os
import json
from livekit.agents import JobContext, llm, WorkerOptions, cli
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import deepgram, cartesia, openai, silero
from app.db import (
    identify_user_db, fetch_slots_db, book_appointment_db,
    retrieve_appointments_db, cancel_appointment_db, modify_appointment_db
)

# We wrap your database functions in LiveKit's @llm.ai_callable decorators.
# This exposes them as tools the AI can trigger mid-conversation.
class ClinicAssistant(llm.FunctionContext):
    def __init__(self, room):
        super().__init__()
        self.room = room

    async def broadcast_ui_status(self, state: str, message: str):
        """Sends live status updates directly to the frontend UI panel."""
        payload = json.dumps({"status": state, "msg": message})
        await self.room.local_participant.publish_data(payload)

    @llm.ai_callable(description="Resolves user ID by matching phone numbers.")
    async def identify_user(self, phone_number: str, name: str = None):
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
        if result["status"] == "conflict":
            await self.broadcast_ui_status("conflict", "Slot taken! Re-checking...")
        else:
            await self.broadcast_ui_status("success", f"Booking confirmed for {date} at {time} ✅")
        return json.dumps(result)

async def entrypoint(ctx: JobContext):
    """The main entrypoint that runs when a user connects via the frontend."""
    await ctx.connect()
    print(f"🔗 Connected to WebRTC Room: {ctx.room.name}")

    fnc_ctx = ClinicAssistant(ctx.room)

    # Build the real-time AI pipeline
    agent = VoicePipelineAgent(
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        # We use the standard OpenAI plugin, but route it to Google's Gemini endpoint
        llm=openai.LLM(
            model="gemini-1.5-flash", 
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/", 
            api_key=os.getenv("GEMINI_API_KEY")
        ),
        tts=cartesia.TTS(),
        fnc_ctx=fnc_ctx,
        chat_ctx=llm.ChatContext().append(
            role="system",
            text=(
                "You are a polite, efficient healthcare receptionist at Mykare Clinic. "
                "Keep responses brief and conversational. "
                "Always confirm phone numbers digit-by-digit before searching."
            )
        )
    )

    agent.start(ctx.room)
    await agent.say("Hi, this is the Mykare Clinic assistant. How can I help you today?", allow_interruptions=True)

if __name__ == "__main__":
    # This allows us to run the worker from the command line
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))