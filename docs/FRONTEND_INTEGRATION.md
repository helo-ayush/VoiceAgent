# Voice Agent Frontend Integration & Handshake Guide

This guide details how to integrate your frontend application (Web, Mobile, or Desktop) with the **VoiceAgent** backend FastAPI service and the LiveKit WebRTC room.

---

## 🔌 1. The Dynamic Handshake Pattern

To initiate a call, the client frontend MUST perform a handshake with the token server. This endpoint dynamically allocates a unique room, assigns a unique participant identity, and seals the client's configuration preferences inside the signed JWT metadata.

### Token Request Contract
* **Method**: `GET`
* **Path**: `/getToken`
* **Query Parameters**:
  - `personality` (string, optional): `"neutral" | "savage" | "genz"` (default: `"neutral"`)
  - `llm` (string, optional): `"openai" | "groq"` (default: `"openai"`)
  - `stt` (string, optional): `"deepgram" | "sarvam" | "groq-whisper-v3" | "groq-whisper-turbo"` (default: `"deepgram"`)

### Response Payload Structure
```json
{
  "serverUrl": "wss://your-livekit-url-here.com",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJncmFudHMiOnsiYWN0aXZpdHkiOn..."
}
```

---

## ⚛️ 2. React LiveKit Integration

Integrate the LiveKit WebRTC hooks inside your React component structure using the official `@livekit/components-react` library.

### Basic Setup Example
```jsx
import { LiveKitRoom, RoomAudioRenderer } from "@livekit/components-react";

function VoiceCallContainer({ serverUrl, token, sttProvider }) {
  return (
    <LiveKitRoom
      serverUrl={serverUrl}
      token={token}
      connect={true}
      audio={{
        echoCancellation: true,    // Essential: prevents speaker audio loops
        noiseSuppression: true,    // Suppresses basic ambient room noise
        autoGainControl: true,     // Normalizes participant speaking levels
      }}
      onDisconnected={() => console.log("Call terminated.")}
    >
      {/* 1. Main Client Voice Assistant controller component */}
      <VoiceAssistantDashboard sttProvider={sttProvider} />
      
      {/* 2. Renders incoming audio tags to hear the agent's voice */}
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}
```

---

## 🔇 3. Client-Side Enterprise Noise Suppression (Krisp)

For production deployments, standard browser-level noise suppression is often insufficient. We integrate the `@livekit/krisp-noise-filter` package to execute deep neural network noise suppression locally on the browser thread.

### Krisp Audio Processor Binding
```javascript
import { useEffect } from "react";
import { useTracks } from "@livekit/components-react";
import { Track } from "livekit-client";
import { KrispNoiseFilter } from "@livekit/krisp-noise-filter";

function useClientNoiseCancellation() {
  const localTracks = useTracks([Track.Source.Microphone]);
  const localMicTrack = localTracks.find((t) => t.participant.isLocal);

  useEffect(() => {
    if (localMicTrack?.publication?.track) {
      // Instantiate neural processor
      const krispFilter = KrispNoiseFilter();
      
      // Bind processor to microphone track pipeline
      localMicTrack.publication.track.setProcessor(krispFilter)
        .then(() => console.log("Krisp Neural NC successfully applied to mic!"))
        .catch((err) => console.warn("Krisp initialization skipped:", err));
    }
  }, [localMicTrack]);
}
```

---

## 📊 4. Consuming Real-Time Performance Metrics

The voice agent monitors pipeline latencies (STT delay, LLM TTFT, and TTS TTFB) and broadcasts these metrics over a custom WebRTC data channel topic (`agent_metrics`).

### Data Channel Subscriber Setup
```javascript
import { useState } from "react";
import { useDataChannel } from "@livekit/components-react";

function MetricsViewer() {
  const [latencies, setLatencies] = useState({ stt: 0, llm: 0, tts: 0 });

  useDataChannel((message) => {
    // 1. Filter events matching our specific agent telemetry topic
    if (message.topic === "agent_metrics") {
      try {
        // 2. Decode the raw binary payload array into string format
        const decodedText = new TextDecoder().decode(message.payload);
        const data = JSON.parse(decodedText);
        
        // 3. Populate metrics: data.type = "stt" | "llm" | "tts", data.latency = duration in ms
        setLatencies((prev) => ({ ...prev, [data.type]: data.latency }));
      } catch (err) {
        console.error("Failed to parse telemetry packet:", err);
      }
    }
  });

  return (
    <div className="latency-dashboard">
      <div>STT Transcription Delay: {latencies.stt}ms</div>
      <div>LLM Cognitive Think Time: {latencies.llm}ms</div>
      <div>TTS Speech Synthesis Time: {latencies.tts}ms</div>
    </div>
  );
}
```

---

## 🎨 5. Creating Custom Oscilloscope Canvas Visualizers

To create a fluid, premium visual interface, we avoid static visualizers. The frontend extracts real-time PCM audio arrays from the WebRTC track, feeding them into the browser **Web Audio API** to render an oscilloscope waveform inside an HTML5 `<canvas>`.

### Custom Canvas Visualizer Component
```jsx
import { useEffect, useRef } from "react";
import { useVoiceAssistant } from "@livekit/components-react";

export function CanvasVisualizer({ trackRef, color }) {
  const canvasRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const animationFrameRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    // Extract the raw WebRTC MediaStreamTrack
    let mediaStreamTrack = null;
    if (trackRef?.publication?.track?.mediaStreamTrack) {
      mediaStreamTrack = trackRef.publication.track.mediaStreamTrack;
    } else if (trackRef?.track?.mediaStreamTrack) {
      mediaStreamTrack = trackRef.track.mediaStreamTrack;
    }

    // Render resting state flat line if stream is inactive
    if (!mediaStreamTrack) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.lineWidth = 2;
      ctx.strokeStyle = color;
      ctx.beginPath();
      ctx.moveTo(0, canvas.height / 2);
      ctx.lineTo(canvas.width, canvas.height / 2);
      ctx.stroke();
      return;
    }

    // Initialize Web Audio pipeline
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    audioCtxRef.current = audioContext;

    const source = audioContext.createMediaStreamSource(new MediaStream([mediaStreamTrack]));
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 512; // Controls frequency bin sizing (power of 2)
    analyserRef.current = analyser;

    source.connect(analyser);

    // Byte array to hold real-time time-domain amplitude levels
    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    const renderFrame = () => {
      if (!canvasRef.current || !analyserRef.current) return;
      const width = canvas.width;
      const height = canvas.height;

      // Extract raw PCM bytes (ranges from 0 to 255, quiet center point is 128)
      analyserRef.current.getByteTimeDomainData(dataArray);

      ctx.clearRect(0, 0, width, height);
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = color;
      ctx.beginPath();

      const sliceWidth = width / dataArray.length;
      let x = 0;
      let amplitudeSum = 0;

      for (let i = 0; i < dataArray.length; i++) {
        const value = dataArray[i] / 128.0; // Normalizes amplitudes around 1.0
        const y = (value * height) / 2;     // Translate to Y coordinate along canvas height
        
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        
        x += sliceWidth;
        amplitudeSum += Math.abs(128 - dataArray[i]); // Sum off-center offsets for intensity
      }
      
      ctx.lineTo(width, height / 2);

      // Add a modern neon glow effect when peak volumes are hit
      if (amplitudeSum > 500) {
        ctx.shadowBlur = 8;
        ctx.shadowColor = color;
      } else {
        ctx.shadowBlur = 0;
      }

      ctx.stroke();

      // Trigger recursion synchronized with browser screen refreshes
      animationFrameRef.current = requestAnimationFrame(renderFrame);
    };

    renderFrame();

    // Clean up Web Audio API processes on component unmount
    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      if (audioCtxRef.current) audioCtxRef.current.close();
    };
  }, [trackRef]);

  return <canvas ref={canvasRef} width={400} height={100} className="visualizer-canvas" />;
}
```
