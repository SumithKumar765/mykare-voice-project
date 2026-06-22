# Mykare Front-Desk AI

An end-to-end, real-time voice AI receptionist built for healthcare clinics. The system combines agentic AI, WebRTC, and a visual avatar to handle patient interactions, manage appointments, and log call summaries autonomously.

---

## 🚀 Features Achieved

- **Ultra-Low Latency Voice Pipeline** — Seamless conversational flow powered by Deepgram (STT), Groq (LLM), and Cartesia (TTS) over LiveKit WebRTC.
- **Interactive Visual Avatar** — Real-time lip-syncing and visual presence powered by Simli AI.
- **Agentic Tool Execution** — The AI autonomously queries and writes to a Supabase (PostgreSQL) database in real time to:
  - Identify existing users securely
  - Check available appointment slots
  - Book, reschedule, and cancel appointments
- **Intelligent Phone Number Verification** — Digit-by-digit confirmation logic to ensure data integrity before executing database tools.
- **Automated Call Summarization** — Generates and logs structured JSON summaries of the transcript and actions taken as soon as a call ends.
- **Continuous Session Handling** — Stable backend worker state management that supports back-to-back calls without crashing or lagging.

---

## 🛠️ Technology Stack

**Frontend**
- React 18 + Vite
- TypeScript
- LiveKit Components React
- TailwindCSS

**Backend**
- Python 3.12+
- FastAPI
- LiveKit Agents Framework
- Supabase (PostgreSQL)

**AI & Microservices**
- **LLM:** Llama-3.3-70b-versatile & Llama-3.1-8b-instant (via Groq)
- **STT:** Deepgram
- **TTS:** Cartesia
- **Avatar:** Simli AI
- **VAD:** Silero

---

## 💻 Local Setup Guide

### 1. Prerequisites

Make sure you have the following installed:

- [Node.js](https://nodejs.org/) (v18 or higher)
- [Python](https://www.python.org/) (v3.10 – v3.12)
- A [LiveKit Cloud](https://livekit.io/) account
- A [Supabase](https://supabase.com/) project
- API keys for Groq, Deepgram, Cartesia, and Simli

### 2. Backend Setup

```bash
# Navigate to the backend directory
cd backend

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the `backend` directory:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_key
LIVEKIT_API_SECRET=your_secret
GROQ_API_KEY=your_key
DEEPGRAM_API_KEY=your_key
CARTESIA_API_KEY=your_key
SIMLI_API_KEY=your_key
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
```

Start the FastAPI connection server:

```bash
python main.py
```

In a **second terminal**, activate the virtual environment again and start the AI Voice Agent worker:

```bash
python -m app.agent dev
```

### 3. Frontend Setup

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install
```

Create a `.env` file in the `frontend` directory:

```env
VITE_BACKEND_URL=http://localhost:8000
VITE_LIVEKIT_URL=wss://your-project.livekit.cloud
```

Start the development server:

```bash
npm run dev
```

---

## ✅ Verifying the Setup

1. Backend server running on `http://localhost:8000`
2. Agent worker connected and listening (check terminal logs for "registered worker")
3. Frontend running on `http://localhost:5173` (Vite default)
4. Open the frontend in a browser, start a call, and confirm voice .

---

## 📁 Project Structure (high level)

```
mykare-voice-project/
├── backend/
│   ├── app/
│   │   └── agent.py
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   └── lib/
│   └── package.json
└── README.md
```
