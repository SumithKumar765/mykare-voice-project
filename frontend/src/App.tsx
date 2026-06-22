import { useState } from 'react';
import { 
  LiveKitRoom, 
  RoomAudioRenderer, 
  useDataChannel, 
  useRemoteParticipants,
  VideoTrack
} from '@livekit/components-react';
import { Track } from 'livekit-client';
import { Phone, PhoneOff, Disc, Activity } from 'lucide-react';
import { supabase } from './lib/supabase';
import CallSummary, { type SummaryData } from './components/CallSummary';

// --- Tool Listener ---
function ToolStatusListener({ setToolState }: { setToolState: Function }) {
  useDataChannel((msg) => {
    try {
      const data = JSON.parse(new TextDecoder().decode(msg.payload));
      if (data.status && data.msg) setToolState(data);
    } catch (e) {}
  });
  return null;
}

// --- Avatar Video Renderer ---
function AvatarDisplay() {
  const participants = useRemoteParticipants();
  // Find the agent/avatar participant (ignores the local 'Caller')
  const agentParticipant = participants.find((p) => p.identity !== 'Caller');
  
  // Look for a published video track from Simli
  const videoPublication = agentParticipant?.getTrackPublication(Track.Source.Camera);
  const isVideoReady = videoPublication?.isSubscribed && videoPublication?.track;

  if (isVideoReady && videoPublication.track) {
    return (
      <div className="w-full h-full object-cover overflow-hidden rounded-2xl">
        <VideoTrack trackRef={{ participant: agentParticipant, publication: videoPublication, source: Track.Source.Camera }} />
      </div>
    );
  }

  // Fallback UI while Simli is booting up
  return (
    <div className="w-full h-full bg-slate-950 flex flex-col justify-center items-center rounded-2xl">
      <div className="w-32 h-32 rounded-full bg-teal-500 animate-pulse mb-4 flex justify-center items-center">
        <Activity size={48} className="text-white" />
      </div>
      <p className="text-teal-400 font-medium">Voice Stream Active</p>
      <p className="text-slate-500 text-sm mt-2">Waiting for Simli Avatar Video...</p>
    </div>
  );
}

type CallState = 'idle' | 'active' | 'fetching_summary' | 'summary_ready';

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [callState, setCallState] = useState<CallState>('idle');
  const [summaryData, setSummaryData] = useState<SummaryData | null>(null);
  const [toolState, setToolState] = useState({ status: 'idle', msg: 'Ready to establish call infrastructure...' });

  const startCall = async () => {
    try {
      setToolState({ status: 'pending', msg: 'Connecting to backend...' });
      const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}/get-token`);
      const data = await response.json();
      setToken(data.token);
      setCallState('active');
      setToolState({ status: 'success', msg: 'Connected successfully. Agent is listening!' });
    } catch (error) {
      setToolState({ status: 'conflict', msg: 'Failed to reach backend.' });
    }
  };

  const endCall = () => {
    setCallState('fetching_summary');
    setToken(null);
    setToolState({ status: 'idle', msg: 'Call ended. Summary generating...' });
    
    // Allow time for backend to write call logs before fetching
    setTimeout(async () => {
      try {
        const { data } = await supabase.from('call_logs').select('summary').order('id', { ascending: false }).limit(1).single();
        if (data?.summary) {
          setSummaryData(data.summary as SummaryData);
          setCallState('summary_ready');
        } else {
          setCallState('idle');
        }
      } catch (err) {
        setCallState('idle');
      }
    }, 6000);
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col items-center p-6">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-teal-400">Mykare Front-Desk AI</h1>
      </header>

      {callState === 'summary_ready' && summaryData ? (
        <CallSummary summaryData={summaryData} onRestart={() => setCallState('idle')} />
      ) : callState === 'active' && token ? (
        
        /* ACTIVE CALL STATE: Everything wrapped securely inside LiveKitRoom */
        <LiveKitRoom 
          video={true} 
          audio={true} 
          token={token} 
          serverUrl={import.meta.env.VITE_LIVEKIT_URL} 
          onDisconnected={endCall}
          className="w-full max-w-5xl flex-grow flex"
        >
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 w-full">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl shadow-2xl relative flex flex-col justify-center items-center min-h-[350px]">
              <AvatarDisplay />
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6 shadow-2xl flex flex-col justify-between">
              <div>
                <h3 className="text-xl font-semibold mb-4 text-slate-300 flex items-center gap-2">
                  <Disc className="animate-spin text-teal-400" size={20} /> Live Execution Pipeline
                </h3>
                <div className="p-4 rounded-xl border bg-slate-900 border-slate-700 text-slate-400">
                  <span className="block text-xs font-bold uppercase mb-1 opacity-60">System State</span>
                  <p className="font-mono text-sm">{toolState.msg}</p>
                </div>
              </div>
              <div className="mt-6 flex justify-center">
                <button onClick={endCall} className="bg-rose-500 hover:bg-rose-600 text-white font-bold px-8 py-4 rounded-xl shadow-lg w-full flex justify-center gap-3">
                  <PhoneOff size={20} /> Terminate Connection
                </button>
              </div>
            </div>
          </div>
          <RoomAudioRenderer />
          <ToolStatusListener setToolState={setToolState} />
        </LiveKitRoom>

      ) : (

        /* IDLE / FETCHING STATE: LiveKitRoom is unmounted */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 w-full max-w-5xl flex-grow">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl shadow-2xl relative flex flex-col justify-center items-center min-h-[350px]">
            {callState === 'fetching_summary' ? (
              <div className="text-center p-6"><div className="w-12 h-12 border-4 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div><p className="text-slate-400">Generating AI Summary...</p></div>
            ) : (
              <div className="text-center p-6"><p className="text-slate-500">System Offline. Click "Start Call".</p></div>
            )}
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6 shadow-2xl flex flex-col justify-between">
            <div>
              <h3 className="text-xl font-semibold mb-4 text-slate-300 flex items-center gap-2">
                <Disc className="text-slate-500" size={20} /> Live Execution Pipeline
              </h3>
              <div className="p-4 rounded-xl border bg-slate-900 border-slate-700 text-slate-400">
                <span className="block text-xs font-bold uppercase mb-1 opacity-60">System State</span>
                <p className="font-mono text-sm">{toolState.msg}</p>
              </div>
            </div>
            <div className="mt-6 flex justify-center">
              <button onClick={startCall} className="bg-teal-500 hover:bg-teal-600 text-slate-900 font-bold px-8 py-4 rounded-xl shadow-lg w-full flex justify-center gap-3">
                <Phone size={20} /> Start Front-Desk Call
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}