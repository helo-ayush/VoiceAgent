/**
 * Voice Assistant React Frontend Application.
 * 
 * Provides a clean visual interface for the LiveKit Voice Agent.
 * Handles user preference selection (personality, LLM, STT), makes authorization
 * handshakes with the FastAPI token server, connects to LiveKit Cloud WebRTC rooms,
 * tracks latency metrics, registers client-side noise suppression filters, and
 * renders a custom real-time HTML5 Canvas dual waveform visualizer.
 */

import { useState, useEffect, useRef } from "react";
import { Mic, Square } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LiveKitRoom,
  useVoiceAssistant,
  RoomAudioRenderer,
  useConnectionState,
  useLocalParticipant,
  useTracks,
  useDataChannel,
  ConnectionQualityIndicator,
  useRoomContext
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { KrispNoiseFilter } from "@livekit/krisp-noise-filter";
import "@livekit/components-styles";

function App() {
  // State variables for tracking the WebRTC tokens and connection status
  const [connectionDetails, setConnectionDetails] = useState(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState(null);
  
  // Dynamic agent configurations populated by drop-down menus
  const [personality, setPersonality] = useState("neutral");
  const [llm, setLlm] = useState("openai");
  const [stt, setStt] = useState("deepgram");

  /**
   * Action Handler: Fetches access tokens and boots the room session.
   */
  const connect = async () => {
    try {
      setIsConnecting(true);
      setError(null);
      
      // Serialize selection state into REST query parameters
      const params = new URLSearchParams({ personality, llm, stt });
      
      // Request signed JWT from our FastAPI server
      const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}/getToken?${params}`);
      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      // Store server token parameters and trigger LiveKitRoom component mount
      setConnectionDetails({ ...data, sttProvider: stt });
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to fetch token from backend.");
    } finally {
      setIsConnecting(false);
    }
  };

  /**
   * Cleans the active connection state to unmount the LiveKitRoom and close WebRTC sockets.
   */
  const disconnect = () => {
    setConnectionDetails(null);
  };

  return (
    <div className="h-screen w-full bg-[#FDFCF8] text-neutral-900 font-sans overflow-hidden flex flex-col selection:bg-neutral-200">

      {/* Main minimal stage */}
      <main className="flex-1 w-full max-w-4xl mx-auto flex flex-col pt-8 pb-32 px-4 md:px-8 relative z-10 overflow-hidden">

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 text-red-600 p-4 rounded-xl text-sm border border-red-200 mb-4 text-center">
            {error}
          </div>
        )}

        {/* 
          LiveKit Room Container.
          Handles standard audio pre-processing and initiates WebRTC peer connections.
        */}
        {connectionDetails ? (
          <LiveKitRoom
            serverUrl={connectionDetails.serverUrl}
            token={connectionDetails.token}
            connect={true}
            audio={{
              echoCancellation: true,    // Browser AEC
              noiseSuppression: true,    // Browser standard NC
              autoGainControl: true,     // Normalizes microphone gain levels
            }}
            onDisconnected={disconnect}
            className="flex-1 flex flex-col w-full relative"
          >
            {/* Renders the inner voice call UI panels */}
            <VoiceAssistantUI sttProvider={connectionDetails.sttProvider} />
            
            {/* Standard audio tag renderer required to play incoming WebRTC voice streams */}
            <RoomAudioRenderer />
          </LiveKitRoom>
        ) : (
          /* Connect Landing Screen with Configuration Controls */
          <div className="flex-1 flex flex-col items-center justify-center">
            <h1 className="text-2xl font-semibold mb-6">Voice Assistant</h1>
            <p className="text-neutral-500 mb-8 text-center max-w-md">
              Configure your agent and click connect to spawn an isolated instance.
            </p>

            <div className="flex flex-wrap justify-center gap-4 mb-8">
              {/* Personality Dropdown */}
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-neutral-600">Personality</label>
                <select
                  value={personality}
                  onChange={(e) => setPersonality(e.target.value)}
                  className="px-4 py-2 bg-white border border-neutral-200 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-neutral-900"
                >
                  <option value="neutral">Helpful Friend</option>
                  <option value="savage">Sarcastic Roaster</option>
                  <option value="genz">Hyper Gen-Z</option>
                </select>
              </div>

              {/* LLM Engine Dropdown */}
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-neutral-600">LLM Provider</label>
                <select
                  value={llm}
                  onChange={(e) => setLlm(e.target.value)}
                  className="px-4 py-2 bg-white border border-neutral-200 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-neutral-900"
                >
                  <option value="openai">OpenAI (GPT-4o)</option>
                  <option value="groq">Groq (openai/gpt-oss-120b)</option>
                </select>
              </div>

              {/* Speech-To-Text Dropdown */}
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-neutral-600">STT Provider</label>
                <select
                  value={stt}
                  onChange={(e) => setStt(e.target.value)}
                  className="px-4 py-2 bg-white border border-neutral-200 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-neutral-900"
                >
                  <option value="deepgram">Deepgram (hi)</option>
                  <option value="sarvam">Sarvam (Hinglish)</option>
                  <option value="groq-whisper-v3">Groq Whisper V3</option>
                  <option value="groq-whisper-turbo">Groq Whisper Turbo</option>
                </select>
              </div>
            </div>
          </div>
        )}

      </main>

      {/* Bottom Floating Control Panel (Connect / Disconnect Button) */}
      <footer className="fixed bottom-0 left-0 w-full pb-8 flex justify-center items-center z-50 bg-gradient-to-t from-[#FDFCF8] to-transparent pt-10">
        <div className="relative flex items-center justify-center">
          <button
            onClick={connectionDetails ? disconnect : connect}
            disabled={isConnecting}
            className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all duration-500 shadow-[0_8px_30px_rgb(0,0,0,0.06)] hover:shadow-[0_12px_40px_rgb(0,0,0,0.08)] focus:outline-none focus:ring-2 focus:ring-offset-4 focus:ring-offset-[#FDFCF8]
              ${connectionDetails
                ? "bg-white text-red-500"
                : "bg-neutral-900 text-white hover:bg-neutral-800"
              } ${isConnecting ? "opacity-50 cursor-not-allowed" : ""}`
            }
          >
            {connectionDetails ? <Square className="w-8 h-8 fill-current" /> : <Mic className="w-8 h-8 opacity-90" />}
          </button>
        </div>
      </footer>
    </div>
  );
}

// ─── Inner UI Components (Executed inside LiveKit Room Context) ───

function VoiceAssistantUI({ sttProvider = "deepgram" }) {
  const getSttLabel = (provider) => {
    if (provider === "sarvam") return "Sarvam";
    if (provider === "groq-whisper-v3") return "Groq V3";
    if (provider === "groq-whisper-turbo") return "Groq Turbo";
    return "Deepgram";
  };
  const sttLabel = getSttLabel(sttProvider);
  
  // Access connection, speech, and state hooks from LiveKit React SDK
  const { state, audioTrack } = useVoiceAssistant();
  const connectionState = useConnectionState();
  const { localParticipant } = useLocalParticipant();

  // State to hold and print live pipeline execution latencies (broadcast from the agent worker)
  const [metrics, setMetrics] = useState({ stt: 0, llm: 0, tts: 0 });

  // WebRTC custom data channel listener. Reads system updates dynamically.
  useDataChannel((msg) => {
    if (msg.topic === "agent_metrics") {
      console.log("RECEIVED METRICS MSG:", msg);
      try {
        const data = JSON.parse(new TextDecoder().decode(msg.payload));
        // Parse and populate latest latencies into local state variables
        setMetrics((prev) => ({ ...prev, [data.type]: data.latency }));
      } catch (e) {
        console.error("Failed to parse agent metrics packet", e);
      }
    }
  });

  // Fetch local microphone track references
  const localTracks = useTracks([Track.Source.Microphone]);
  const localMicTrack = localTracks.find((t) => t.participant.isLocal);

  // Client-Side Noise Cancellation:
  // Dynamically load and inject the advanced Krisp Noise Filter processor onto the mic stream.
  useEffect(() => {
    if (localMicTrack?.publication?.track) {
      const krisp = KrispNoiseFilter();
      localMicTrack.publication.track.setProcessor(krisp).catch((e) => {
        console.warn("Krisp noise filter could not be loaded on client browser:", e);
      });
    }
  }, [localMicTrack]);

  // Helper method to convert state flags into readable status tags
  const getStatusText = () => {
    if (connectionState === "connecting") return "Connecting...";
    if (state === "listening") return "Listening...";
    if (state === "speaking") return "AI is speaking...";
    if (state === "thinking") return "Thinking...";
    return "Connected";
  };

  return (
    <div className="flex-1 flex flex-col justify-end items-center w-full relative pb-10">

      {/* Network Connectivity & Latency Metrics Dashboard */}
      <div className="absolute top-0 left-0 flex flex-col gap-3">
        {connectionState === "connected" && (
          <>
            <div className="flex items-center gap-2 bg-white/50 backdrop-blur-md border border-neutral-200 px-3 py-1.5 rounded-full text-xs font-medium text-neutral-600 shadow-sm">
              <ConnectionQualityIndicator participant={localParticipant} />
              <span>LiveKit Network</span>
            </div>
            
            {/* Speech-To-Text Metric Card */}
            <div className="flex items-center gap-2 bg-white/50 backdrop-blur-md border border-neutral-200 px-3 py-1.5 rounded-full text-xs font-medium text-neutral-600 shadow-sm">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              <span>STT ({sttLabel}): {metrics.stt > 0 ? `${metrics.stt}ms` : "-"}</span>
            </div>
            
            {/* LLM Generation TTFT Metric Card */}
            <div className="flex items-center gap-2 bg-white/50 backdrop-blur-md border border-neutral-200 px-3 py-1.5 rounded-full text-xs font-medium text-neutral-600 shadow-sm">
              <span className="w-2 h-2 rounded-full bg-purple-500" />
              <span>LLM (TTFT): {metrics.llm > 0 ? `${metrics.llm}ms` : "-"}</span>
            </div>
            
            {/* Text-To-Speech Synthesis TTFB Metric Card */}
            <div className="flex items-center gap-2 bg-white/50 backdrop-blur-md border border-neutral-200 px-3 py-1.5 rounded-full text-xs font-medium text-neutral-600 shadow-sm">
              <span className="w-2 h-2 rounded-full bg-orange-500" />
              <span>TTS (TTFB): {metrics.tts > 0 ? `${metrics.tts}ms` : "-"}</span>
            </div>
          </>
        )}
      </div>

      {/* Waveform Visualizer Wrapper */}
      <div className="w-full flex flex-col items-center justify-center opacity-80 relative">
        <div className="flex items-center justify-center gap-2 text-xs font-semibold text-neutral-400 tracking-widest uppercase mb-2 z-10">
          {connectionState === "connected" && (
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
          )}
          {getStatusText()}
        </div>

        {/* Dual Overlapping HTML5 Canvas Waveforms */}
        <div className="h-24 w-full max-w-sm flex items-center justify-center relative">

          {/* User microphone visualizer (gray glow) */}
          <div className="absolute inset-0 flex items-center justify-center opacity-50">
            <CanvasVisualizer
              trackRef={localMicTrack}
              color="#9ca3af" // Tailwind gray-400
            />
          </div>

          {/* Agent incoming voice visualizer (blue glow) */}
          <div className="absolute inset-0 flex items-center justify-center mix-blend-multiply">
            <CanvasVisualizer
              trackRef={audioTrack}
              color="#3b82f6" // Tailwind blue-500
            />
          </div>

        </div>
      </div>
    </div>
  );
}

// ─── Custom HTML5 Canvas Waveform Visualizer (PCM Domain Analyzer) ───

function CanvasVisualizer({ trackRef, color }) {
  const canvasRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const sourceRef = useRef(null);
  const animationFrameRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    let mediaStreamTrack = null;
    let localStream = null;

    /**
     * Extracts browser WebRTC media stream tracks and initializes the Web Audio API context.
     */
    const setupAudio = async () => {
      // 1. Fetch raw audio streams
      if (trackRef === "local") {
        try {
          localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          mediaStreamTrack = localStream.getAudioTracks()[0];
        } catch (e) {
          console.error("Mic access denied for custom canvas visualizer:", e);
        }
      } else if (trackRef?.publication?.track?.mediaStreamTrack) {
        mediaStreamTrack = trackRef.publication.track.mediaStreamTrack;
      } else if (trackRef?.track?.mediaStreamTrack) {
        mediaStreamTrack = trackRef.track.mediaStreamTrack;
      }

      // If no track is present yet, render a silent resting horizontal line
      if (!mediaStreamTrack) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.lineWidth = 2;
        ctx.strokeStyle = color;
        ctx.shadowBlur = 0;
        ctx.beginPath();
        ctx.moveTo(0, canvas.height / 2);
        ctx.lineTo(canvas.width, canvas.height / 2);
        ctx.stroke();
        return;
      }

      // 2. Instantiate and wire Web Audio API pipeline components
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      audioContextRef.current = audioContext;

      const mediaStream = new MediaStream([mediaStreamTrack]);
      const source = audioContext.createMediaStreamSource(mediaStream);
      sourceRef.current = source;

      // Instantiate Web Audio Analyser Node
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;          // Sets the sizing of Fast Fourier Transform bins
      analyserRef.current = analyser;

      source.connect(analyser);

      // Raw array to hold real-time PCM Byte Time Domain amplitude values
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      /**
       * Loop method synced with browser refresh cycles (requestAnimationFrame).
       * Renders the wavy oscilliscope path in real-time.
       */
      const drawWaveform = () => {
        if (!canvasRef.current || !analyserRef.current) return;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");
        const width = canvas.width;
        const height = canvas.height;

        // Fetch latest time domain amplitudes (values range from 0 to 255, silent at 128)
        analyserRef.current.getByteTimeDomainData(dataArray);

        ctx.clearRect(0, 0, width, height);
        ctx.lineWidth = 2;
        ctx.strokeStyle = color;
        ctx.beginPath();

        const sliceWidth = width / dataArray.length;
        let x = 0;
        let sum = 0;
        
        // Loop over the PCM array to plot coordinates
        for (let i = 0; i < dataArray.length; i++) {
          const v = dataArray[i] / 128.0;      // Normalize amplitudes (around 1.0)
          const y = (v * height) / 2;          // Project coordinate along canvas heights
          
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
          
          x += sliceWidth;
          sum += Math.abs(128 - dataArray[i]); // Sum off-center offsets to track loudness
        }
        
        ctx.lineTo(width, height / 2);

        // Add subtle neon glow effect when loudness exceeds threshold
        if (sum > 500) {
          ctx.shadowBlur = 4;
          ctx.shadowColor = color;
        } else {
          ctx.shadowBlur = 0;
        }

        ctx.stroke();

        // Recursively trigger next frame draw
        animationFrameRef.current = requestAnimationFrame(drawWaveform);
      };

      drawWaveform();
    };

    setupAudio();

    // Clean up Web Audio resources on unmount
    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      if (sourceRef.current) sourceRef.current.disconnect();
      if (audioContextRef.current) audioContextRef.current.close();
      if (localStream) {
        localStream.getTracks().forEach(t => t.stop());
      }
    };
  }, [trackRef, trackRef?.publication?.track, trackRef?.track, trackRef?.publication?.track?.mediaStreamTrack, trackRef?.track?.mediaStreamTrack]);

  return (
    <canvas
      ref={canvasRef}
      width={400}
      height={100}
      className="w-full h-full object-contain"
    />
  );
}

export default App;