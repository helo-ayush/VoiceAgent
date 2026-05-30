"""
FastAPI Token Distribution Server.

Exposes a REST API interface that handshakes with client frontends.
This server generates secure JWT Access Tokens using secret keys, granting
browser clients WebRTC authorization to join dynamic, isolated LiveKit rooms.
Additionally, it packages user preferences (personality, LLM, STT) directly
into the participant's metadata, enabling real-time config inheritance by the agent.
"""

import os
import uuid
import json
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants

# Load Environment Variables from local .env configuration file
# This enables access to environment-specific credentials like LiveKit keys and host URLs.
load_dotenv()

# Initialize FastAPI instance which acts as our backend REST API server.
app = FastAPI()

# ------------------------------------------------------------------------------
# HEALTH CHECK ROUTE
# ------------------------------------------------------------------------------
# A simple heartbeat health check endpoint, primary used by hosting providers
# (like Hugging Face Spaces or AWS) to monitor container initialization and status.
@app.get("/")
async def health():
    return {"status": "ok", "service": "voice-agent"}

# ------------------------------------------------------------------------------
# CORS (Cross-Origin Resource Sharing) MIDDLEWARE
# ------------------------------------------------------------------------------
# Configures browser cross-origin accessibility policies. This allows developers
# running frontends on separate dev servers (e.g. Vite running on localhost:5173)
# to call the token generation endpoint without experiencing CORS authorization failures.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any origin; restrict to specific domains in production!
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all HTTP headers
)

# ------------------------------------------------------------------------------
# LIVEKIT TOKEN GENERATION ENDPOINT
# ------------------------------------------------------------------------------
# Handshakes with the frontend to securely register a user session.
# Parameters (personality, llm, stt) are passed via URL query parameters, serialized,
# and encrypted directly into the LiveKit participant metadata payload.
@app.get("/getToken")
async def get_token(personality: str = "neutral", llm: str = "openai", stt: str = "deepgram"):
    # 1. Generate a globally unique room name for this specific connection.
    #    This isolates each user connection into their own individual WebRTC room.
    room_name = f"room-user-{uuid.uuid4().hex[:8]}"
    
    # 2. Assign a unique client identity to the browser participant joining the room.
    #    This ensures no conflicts if multiple tabs or users are active.
    participant_identity = f"user-{uuid.uuid4().hex[:4]}"

    # Extract LiveKit API details securely from environment variables.
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    server_url = os.getenv("LIVEKIT_URL")

    # Guard clause to ensure all server keys are active before attempting token creation.
    if not api_key or not api_secret:
        return {"error": "Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET on the server config."}

    # 3. Create a JSON metadata payload.
    #    This metadata acts as the "handshake carrier". When the LiveKit backend agent
    #    notices a user join, it reads this metadata to dynamically boot the chosen configuration.
    metadata = json.dumps({"personality": personality, "llm": llm, "stt": stt})

    # 4. Programmatically construct the JWT Access Token with permissions to join the dynamic room.
    token = AccessToken(
        api_key,
        api_secret
    ).with_identity(participant_identity) \
     .with_name("Human") \
     .with_metadata(metadata) \
     .with_grants(VideoGrants(
         room_join=True,       # Grant join permissions
         room=room_name,       # Explicitly restrict permissions to this room ONLY
     ))

    # Return server connectivity details and the signed JWT payload back to the client.
    return {
        "serverUrl": server_url,
        "token": token.to_jwt()
    }

