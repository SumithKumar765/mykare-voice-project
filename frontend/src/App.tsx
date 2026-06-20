import React, { useState } from 'react';
import { LiveKitRoom, RoomAudioRenderer, useDataChannel } from '@livekit/components-react';
import { Phone, PhoneOff, Disc, Activity } from 'lucide-react';

// Listens for live status updates from your Python backend
function ToolStatusListener({ setToolState }: { setToolState: Function }) {
  useDataChannel((msg) => {
    try {
      const decoder = new TextDecoder();
      const payload = decoder.decode(msg.payload);
      const data = JSON.parse(payload);
      if (data.status && data.msg) {
        setToolState(data);
      }
    } catch (e) {
      console.error("Error decoding tool status:", e);
    }
  });
  return null;
}

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [activeCall, setActiveCall] = useState(false);
  const [toolState, setToolState] = useState({
    status: 'idle',
    msg: 'Ready to establish call infrastructure...'
  });

  const liveKitUrl = import.meta.env.VITE_LIVEKIT_URL;

  const startCall = async () => {
    try {
      setToolState({ status: 'pending', msg: 'Connecting to backend...' });
      
      const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}/get-token`);
      const data = await response.json();
      
      setToken(data.token);
      setActiveCall(true);
      setToolState({ status: 'success', msg: 'Connected successfully. Agent is listening!' });
    } catch (error) {
      console.error("Failed to connect:", error);
      setToolState({ status: 'conflict', msg: 'Failed to reach FastAPI backend.' });
    }
  };

  const endCall = () => {
    setActiveCall(false);
    setToken(null);
    setToolState({ status: 'idle', msg: 'Call ended. Summary generating...' });
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col items-center p-6">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-teal-400">Mykare Front-Desk AI</h1>
        <p className="text-sm text-slate-400">Conversational Voice Agent</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 w-full max-w-5xl flex-grow">
        {/* AVATAR INTERFACE */}
        <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden shadow-2xl relative flex flex-col justify-center items-center min-h-[350px]">
          {activeCall ? (
            <div className="w-full h-full bg-slate-950 flex flex-col justify-center items-center">
              <div className="w-32 h-32 rounded-full bg-teal-500 animate-pulse mb-4 flex items-center justify-center">
                <Activity size={48} className="text-white" />
              </div>
              <p className="text-teal-400 font-medium">Voice Stream Active</p>
            </div>
          ) : (
            <div className="text-center p-6">
              <p className="text-slate-500">System Offline. Click "Start Call" below.</p>
            </div>
          )}
        </div>

        {/* TOOL-CALL STATUS MONITOR */}
        <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6 shadow-2xl flex flex-col justify-between">
          <div>
            <h3 className="text-xl font-semibold mb-4 text-slate-300 flex items-center gap-2">
              <Disc className={`transition-all ${activeCall ? 'animate-spin text-teal-400' : 'text-slate-500'}`} size={20} />
              Live Execution Pipeline
            </h3>
            
            <div className={`p-4 rounded-xl border transition-all duration-300 ${
              toolState.status === 'pending' ? 'bg-amber-950/40 border-amber-500/50 text-amber-300' :
              toolState.status === 'success' ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300' :
              toolState.status === 'conflict' ? 'bg-rose-950/40 border-rose-500/50 text-rose-300' :
              'bg-slate-900 border-slate-700 text-slate-400'
            }`}>
              <span className="block text-xs font-bold uppercase tracking-wider mb-1 opacity-60">System Current State</span>
              <p className="font-mono text-sm">{toolState.msg}</p>
            </div>
          </div>

          <div className="mt-6 flex justify-center">
            {!activeCall ? (
              <button 
                onClick={startCall} 
                className="bg-teal-500 hover:bg-teal-600 text-slate-900 font-bold px-8 py-4 rounded-xl shadow-lg transition-all transform hover:-translate-y-0.5 flex items-center gap-3 w-full justify-center"
              >
                <Phone size={20} /> Start Front-Desk Call
              </button>
            ) : (
              <button 
                onClick={endCall} 
                className="bg-rose-500 hover:bg-rose-600 text-white font-bold px-8 py-4 rounded-xl shadow-lg transition-all transform hover:-translate-y-0.5 flex items-center gap-3 w-full justify-center"
              >
                <PhoneOff size={20} /> Terminate Connection
              </button>
            )}
          </div>
        </div>
      </div>

      {/* LIVEKIT ROOM ENGINE */}
      {activeCall && token && (
        <LiveKitRoom
          video={false}
          audio={true}
          token={token}
          serverUrl={liveKitUrl}
          onDisconnected={endCall}
        >
          <RoomAudioRenderer />
          <ToolStatusListener setToolState={setToolState} />
        </LiveKitRoom>
      )}
    </div>
  );
}