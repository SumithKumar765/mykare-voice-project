import React from 'react';

// EXPORT ADDED HERE: Defines the shape of a single appointment
export interface Appointment {
  date: string;
  time: string;
  status: 'booked' | 'cancelled' | 'modified';
}

// EXPORT ADDED HERE: Defines the shape of the entire JSON summary from Groq
export interface SummaryData {
  summary: string;
  appointments: Appointment[];
  preferences: string[];
  timestamp: string;
}

// Defines the props passed into this specific component
interface CallSummaryProps {
  summaryData: SummaryData | null;
  onRestart: () => void;
}

export default function CallSummary({ summaryData, onRestart }: CallSummaryProps) {
  // If there's no data yet, don't render anything
  if (!summaryData) return null;

  return (
    <div className="w-full max-w-2xl mt-4 p-8 bg-white rounded-2xl shadow-xl border border-gray-100">
      <div className="flex justify-between items-center mb-6 border-b border-gray-100 pb-4">
        <h2 className="text-3xl font-extrabold text-gray-900">Call Summary</h2>
        <span className="text-sm text-gray-400 font-mono">
          {new Date(summaryData.timestamp).toLocaleTimeString()}
        </span>
      </div>
      
      {/* 1. Natural Language Recap */}
      <div className="mb-8 p-5 bg-blue-50/50 rounded-xl border border-blue-100">
        <h3 className="text-sm font-bold text-blue-900 uppercase tracking-wider mb-2">AI Recap</h3>
        <p className="text-gray-700 leading-relaxed">{summaryData.summary}</p>
      </div>

      {/* 2. Appointments List */}
      <div className="mb-8">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Appointments Handled</h3>
        {summaryData.appointments && summaryData.appointments.length > 0 ? (
          <ul className="space-y-3">
            {summaryData.appointments.map((apt, index) => (
              <li key={index} className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-200 hover:border-blue-300 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 flex items-center justify-center bg-white rounded-full shadow-sm">
                    <span className="text-xl">📅</span>
                  </div>
                  <div>
                    <p className="font-bold text-gray-900">{apt.date}</p>
                    <p className="text-sm text-gray-500">{apt.time}</p>
                  </div>
                </div>
                <span className={`px-4 py-1.5 rounded-full text-sm font-bold capitalize shadow-sm ${
                  apt.status === 'booked' ? 'bg-green-100 text-green-700 border border-green-200' : 
                  apt.status === 'cancelled' ? 'bg-red-100 text-red-700 border border-red-200' : 
                  'bg-yellow-100 text-yellow-700 border border-yellow-200'
                }`}>
                  {apt.status}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="p-4 bg-gray-50 rounded-xl border border-gray-200 text-center">
            <p className="text-gray-500 italic">No appointments were modified during this call.</p>
          </div>
        )}
      </div>

      {/* 3. User Preferences */}
      <div className="mb-8">
        <h3 className="text-lg font-bold text-gray-900 mb-3">Noted Preferences</h3>
        {summaryData.preferences && summaryData.preferences.length > 0 ? (
          <ul className="space-y-2">
            {summaryData.preferences.map((pref, index) => (
              <li key={index} className="flex items-start gap-2 text-gray-600">
                <span className="text-blue-500 mt-0.5">•</span>
                {pref}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-gray-500 italic">No specific preferences noted by the AI.</p>
        )}
      </div>

      {/* Action Button */}
      <button 
        onClick={onRestart} 
        className="w-full py-4 mt-4 bg-gray-900 hover:bg-black text-white text-lg font-bold rounded-xl transition-all shadow-lg hover:shadow-xl"
      >
        Start New Call
      </button>
    </div>
  );
}