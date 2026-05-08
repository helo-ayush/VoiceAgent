import os
import uuid
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants

app = FastAPI()

# Health check for Hugging Face Spaces (pings root to verify container is alive)
@app.get("/")
async def health():
    return {"status": "ok", "service": "voice-agent"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow the Vite dev server to access this
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/getToken")
async def get_token():
    # 1. Create a truly unique room name for this specific user session
    room_name = f"room-user-{uuid.uuid4().hex[:8]}"
    
    # 2. Assign a unique identity to the user in the room
    participant_identity = f"user-{uuid.uuid4().hex[:4]}"

    # Fetch env vars
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    server_url = os.getenv("LIVEKIT_URL")

    if not api_key or not api_secret:
        return {"error": "Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET"}

    # 3. Create the JWT Token with permissions to join ONLY this specific room
    token = AccessToken(
        api_key,
        api_secret
    ).with_identity(participant_identity) \
     .with_name("Human") \
     .with_grants(VideoGrants(
         room_join=True,
         room=room_name,
     ))

    return {
        "serverUrl": server_url,
        "token": token.to_jwt()
    }
