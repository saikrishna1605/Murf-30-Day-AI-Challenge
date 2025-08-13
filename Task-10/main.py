from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
import shutil
from typing import List, Dict, Optional
from datetime import datetime

import assemblyai as aai
import google.generativeai as genai

load_dotenv()

aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

# Configure Gemini API
gemini_api_key = os.getenv("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

app = FastAPI(
    title="Murf TTS API, Audio Uploader, and LLM Integration",
    description="Text-to-Speech API using Murf AI, audio upload functionality, and LLM integration with Google Gemini.",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory chat history store - using global dictionary
# This is a simple datastore as requested for the prototype
chat_history_store: Dict[str, List[Dict]] = {}

# Pydantic models
class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime

class ChatSession(BaseModel):
    session_id: str
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime

class TTSRequest(BaseModel):
    text: str
    voice_id: str = "en-US-natalie"

class TTSResponse(BaseModel):
    audio_url: str
    status: str

class LLMRequest(BaseModel):
    text: str

class LLMResponse(BaseModel):
    response: str
    status: str

# In-memory helper functions for chat history
def get_chat_history(session_id: str) -> List[Dict]:
    """Get chat history for a session from in-memory store"""
    return chat_history_store.get(session_id, [])

def add_message_to_history(session_id: str, role: str, content: str) -> None:
    """Add a message to chat history in memory"""
    if session_id not in chat_history_store:
        chat_history_store[session_id] = []
    
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now()
    }
    
    chat_history_store[session_id].append(message)

def clear_chat_history(session_id: str) -> bool:
    """Clear chat history for a session"""
    if session_id in chat_history_store:
        del chat_history_store[session_id]
        return True
    return False

def get_session_message_count(session_id: str) -> int:
    """Get total message count for a session"""
    return len(chat_history_store.get(session_id, []))

def get_all_sessions() -> List[Dict]:
    """Get all sessions with metadata"""
    sessions = []
    for session_id, messages in chat_history_store.items():
        if messages:  # Only include sessions with messages
            sessions.append({
                "session_id": session_id,
                "message_count": len(messages),
                "created_at": messages[0]["timestamp"] if messages else datetime.now(),
                "updated_at": messages[-1]["timestamp"] if messages else datetime.now()
            })
    return sessions

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r") as file:
        return HTMLResponse(content=file.read(), status_code=200)

@app.post("/transcribe/file")
async def transcribe_file(file: UploadFile = File(...)):
    try:
        config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best)
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(file.file)

        if transcript.status == aai.TranscriptStatus.error:
            raise HTTPException(status_code=500, detail=transcript.error)

        return JSONResponse(content={"transcription": transcript.text})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not transcribe file: {e}")


@app.post("/tts/echo")
async def tts_echo(file: UploadFile = File(...)):
    """
    Echo bot endpoint: transcribes audio and generates speech with Murf AI
    """
    try:
        # Step 1: Transcribe the audio using AssemblyAI
        config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best)
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(file.file)

        if transcript.status == aai.TranscriptStatus.error:
            raise HTTPException(status_code=500, detail=f"Transcription error: {transcript.error}")

        transcribed_text = transcript.text
        if not transcribed_text or transcribed_text.strip() == "":
            raise HTTPException(status_code=400, detail="No speech detected in audio")

        # Step 2: Generate speech using Murf AI
        murf_api_key = os.getenv("MURF_API_KEY")
        
        if not murf_api_key:
            raise HTTPException(status_code=500, detail="MURF_API_KEY not found in environment variables")
        
        murf_api_key = murf_api_key.strip('"\'')
        
        headers = {
            "api-key": murf_api_key,
            "Content-Type": "application/json"
        }
        
        # Using a default voice for echo bot - you can make this configurable
        payload = {
            "text": transcribed_text,
            "voiceId": "en-US-natalie",  # Default voice for echo
            "format": "MP3",
            "sampleRate": 44100
        }
        
        print(f"DEBUG: Echo - Transcribed text: {transcribed_text}")
        print(f"DEBUG: Echo - Sending to Murf API with payload: {payload}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.murf.ai/v1/speech/generate",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            print(f"DEBUG: Echo - Murf API response status: {response.status_code}")
            print(f"DEBUG: Echo - Murf API response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                return JSONResponse(content={
                    "audio_url": result.get("audioFile", ""),
                    "transcription": transcribed_text,
                    "status": "success"
                })
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Murf API error: {response.text}"
                )

    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Echo endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Echo processing failed: {str(e)}")


@app.post("/generate-audio", response_model=TTSResponse)
async def generate_audio(request: TTSRequest):
    murf_api_key = os.getenv("MURF_API_KEY")
    
    if not murf_api_key:
        raise HTTPException(status_code=500, detail="MURF_API_KEY not found in environment variables")
    
    murf_api_key = murf_api_key.strip('"\'')
    
    headers = {
        "api-key": murf_api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "text": request.text,
        "voiceId": request.voice_id,
        "format": "MP3",
        "sampleRate": 44100
    }
    
    print(f"DEBUG: Sending request to Murf API with voice_id: {request.voice_id}")
    print(f"DEBUG: Payload: {payload}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.murf.ai/v1/speech/generate",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            print(f"DEBUG: Response status: {response.status_code}")
            print(f"DEBUG: Response text: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"DEBUG: Success response: {result}")
                return TTSResponse(
                    audio_url=result.get("audioFile", ""),
                    status="success"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Murf API error: {response.text}"
                )
                
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/agent/chat/{session_id}")
async def agent_chat_with_history(session_id: str, file: UploadFile = File(...)):
    """
    Full conversational pipeline with in-memory chat history: Audio -> Transcription -> LLM (with history) -> TTS -> Audio Response
    Day 10: Accept audio input, maintain conversation history per session in memory, and return Murf-generated audio
    """
    try:
        # Step 1: Transcribe the audio using AssemblyAI
        config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best)
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(file.file)

        if transcript.status == aai.TranscriptStatus.error:
            raise HTTPException(status_code=500, detail=f"Transcription error: {transcript.error}")

        transcribed_text = transcript.text
        if not transcribed_text or transcribed_text.strip() == "":
            raise HTTPException(status_code=400, detail="No speech detected in audio")

        print(f"DEBUG: Chat Agent - Session {session_id} - Transcribed text: {transcribed_text}")

        # Step 2: Get chat history for this session from memory
        chat_history = get_chat_history(session_id)

        # Step 3: Add user message to history in memory
        add_message_to_history(session_id, "user", transcribed_text)

        # Step 4: Build conversation context for LLM
        conversation_context = "You are a helpful AI assistant. Please respond in a conversational and concise manner (keep it under 2500 characters to fit TTS limits).\n\nConversation history:\n"
        
        # Include recent conversation history (last 10 messages to avoid token limits)
        recent_history = chat_history[-10:] if len(chat_history) > 10 else chat_history
        for message in recent_history:
            if message["role"] == "user":
                conversation_context += f"User: {message['content']}\n"
            else:
                conversation_context += f"Assistant: {message['content']}\n"
        
        # Add the current user message
        conversation_context += f"User: {transcribed_text}\n"
        conversation_context += f"\nPlease respond to the user's latest message."

        # Step 5: Query Google Gemini LLM with conversation context
        if not gemini_api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        llm_response = model.generate_content(conversation_context)
        
        if not llm_response.text:
            raise HTTPException(status_code=500, detail="No response generated from LLM")
        
        llm_text = llm_response.text.strip()
        print(f"DEBUG: Chat Agent - Session {session_id} - Generated response: {llm_text}")
        
        # Step 6: Add assistant message to history in memory
        add_message_to_history(session_id, "assistant", llm_text)

        # Step 7: Check if response is too long for Murf API (3000 char limit)
        if len(llm_text) > 3000:
            # Truncate and add continuation message
            llm_text = llm_text[:2900] + "... I have more to share, but let me pause here."
            print(f"DEBUG: Chat Agent - LLM response truncated to fit Murf limits")

        # Step 8: Generate speech using Murf AI
        murf_api_key = os.getenv("MURF_API_KEY")
        
        if not murf_api_key:
            raise HTTPException(status_code=500, detail="MURF_API_KEY not found in environment variables")
        
        murf_api_key = murf_api_key.strip('"\'')
        
        headers = {
            "api-key": murf_api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": llm_text,
            "voiceId": "en-US-natalie",  # Using default voice for chat responses
            "format": "MP3",
            "sampleRate": 44100
        }
        
        print(f"DEBUG: Chat Agent - Session {session_id} - Sending to Murf API")
        
        async with httpx.AsyncClient() as client:
            murf_response = await client.post(
                "https://api.murf.ai/v1/speech/generate",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            print(f"DEBUG: Chat Agent - Session {session_id} - Murf API response status: {murf_response.status_code}")
            
            if murf_response.status_code == 200:
                murf_result = murf_response.json()
                
                # Get updated message count
                message_count = get_session_message_count(session_id)
                
                # Return response with session info
                return JSONResponse(content={
                    "audio_url": murf_result.get("audioFile", ""),
                    "transcription": transcribed_text,
                    "llm_response": llm_text,
                    "session_id": session_id,
                    "message_count": message_count,
                    "status": "success"
                })
            else:
                raise HTTPException(
                    status_code=murf_response.status_code,
                    detail=f"Murf API error: {murf_response.text}"
                )

    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Chat agent error for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat agent failed: {str(e)}")


@app.get("/agent/history/{session_id}")
async def get_chat_history_endpoint(session_id: str):
    """
    Get chat history for a specific session from in-memory store
    """
    try:
        chat_history = get_chat_history(session_id)
        message_count = len(chat_history)
        
        # Convert datetime objects to strings for JSON serialization
        serializable_history = []
        for message in chat_history:
            serializable_message = {
                "role": message["role"],
                "content": message["content"],
                "timestamp": message["timestamp"].isoformat() if isinstance(message["timestamp"], datetime) else message["timestamp"]
            }
            serializable_history.append(serializable_message)
        
        return JSONResponse(content={
            "session_id": session_id,
            "messages": serializable_history,
            "message_count": message_count
        })
    except Exception as e:
        print(f"Error getting chat history for session {session_id}: {e}")
        return JSONResponse(content={
            "session_id": session_id,
            "messages": [],
            "message_count": 0,
            "error": str(e)
        })


@app.delete("/agent/history/{session_id}")
async def clear_chat_history_endpoint(session_id: str):
    """
    Clear chat history for a specific session in memory
    """
    try:
        success = clear_chat_history(session_id)
        if success:
            return JSONResponse(content={
                "session_id": session_id,
                "message": "Chat history cleared successfully",
                "status": "success"
            })
        else:
            return JSONResponse(content={
                "session_id": session_id,
                "message": "No history found or already cleared",
                "status": "success"
            })
    except Exception as e:
        print(f"Error clearing chat history for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")


@app.get("/agent/sessions")
async def get_all_sessions():
    """
    Get all chat sessions from in-memory store
    """
    try:
        sessions = get_all_sessions()
        
        # Convert datetime objects to strings for JSON serialization
        serializable_sessions = []
        for session in sessions:
            serializable_session = {
                "session_id": session["session_id"],
                "message_count": session["message_count"],
                "created_at": session["created_at"].isoformat() if isinstance(session["created_at"], datetime) else session["created_at"],
                "updated_at": session["updated_at"].isoformat() if isinstance(session["updated_at"], datetime) else session["updated_at"]
            }
            serializable_sessions.append(serializable_session)
        
        return JSONResponse(content={
            "sessions": serializable_sessions,
            "total_sessions": len(serializable_sessions)
        })
    except Exception as e:
        print(f"Error getting all sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sessions: {str(e)}")


@app.post("/llm/query")
async def llm_query_audio(file: UploadFile = File(...)):
    """
    Full pipeline: Audio -> Transcription -> LLM -> TTS -> Audio Response
    Day 9: Accept audio input, transcribe, query LLM, and return Murf-generated audio
    """
    try:
        # Step 1: Transcribe the audio using AssemblyAI
        config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best)
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(file.file)

        if transcript.status == aai.TranscriptStatus.error:
            raise HTTPException(status_code=500, detail=f"Transcription error: {transcript.error}")

        transcribed_text = transcript.text
        if not transcribed_text or transcribed_text.strip() == "":
            raise HTTPException(status_code=400, detail="No speech detected in audio")

        print(f"DEBUG: LLM Audio Pipeline - Transcribed text: {transcribed_text}")

        # Step 2: Query Google Gemini LLM
        if not gemini_api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Add context to make LLM responses more conversational and concise
        llm_prompt = f"""You are a helpful AI assistant. Please respond to the following in a conversational and concise manner (keep it under 2500 characters to fit TTS limits): 

{transcribed_text}"""
        
        llm_response = model.generate_content(llm_prompt)
        
        if not llm_response.text:
            raise HTTPException(status_code=500, detail="No response generated from LLM")
        
        llm_text = llm_response.text.strip()
        print(f"DEBUG: LLM Audio Pipeline - Generated response: {llm_text}")
        
        # Step 3: Check if response is too long for Murf API (3000 char limit)
        if len(llm_text) > 3000:
            # Truncate and add continuation message
            llm_text = llm_text[:2900] + "... I have more to share, but let me pause here."
            print(f"DEBUG: LLM response truncated to fit Murf limits")

        # Step 4: Generate speech using Murf AI
        murf_api_key = os.getenv("MURF_API_KEY")
        
        if not murf_api_key:
            raise HTTPException(status_code=500, detail="MURF_API_KEY not found in environment variables")
        
        murf_api_key = murf_api_key.strip('"\'')
        
        headers = {
            "api-key": murf_api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": llm_text,
            "voiceId": "en-US-natalie",  # Using default voice for LLM responses
            "format": "MP3",
            "sampleRate": 44100
        }
        
        print(f"DEBUG: LLM Audio Pipeline - Sending to Murf API")
        
        async with httpx.AsyncClient() as client:
            murf_response = await client.post(
                "https://api.murf.ai/v1/speech/generate",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            print(f"DEBUG: LLM Audio Pipeline - Murf API response status: {murf_response.status_code}")
            
            if murf_response.status_code == 200:
                murf_result = murf_response.json()
                return JSONResponse(content={
                    "audio_url": murf_result.get("audioFile", ""),
                    "transcription": transcribed_text,
                    "llm_response": llm_text,
                    "status": "success"
                })
            else:
                raise HTTPException(
                    status_code=murf_response.status_code,
                    detail=f"Murf API error: {murf_response.text}"
                )

    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: LLM audio pipeline error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM audio pipeline failed: {str(e)}")


@app.post("/llm/query/text", response_model=LLMResponse)
async def llm_query_text(request: LLMRequest):
    """
    Query Google Gemini LLM with text input and return the response (kept for backward compatibility)
    """
    try:
        # Check if Gemini API key is configured
        if not gemini_api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
        
        # Initialize the Gemini model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        print(f"DEBUG: LLM Query - Input text: {request.text}")
        
        # Generate response from Gemini
        response = model.generate_content(request.text)
        
        if not response.text:
            raise HTTPException(status_code=500, detail="No response generated from LLM")
        
        print(f"DEBUG: LLM Query - Generated response: {response.text}")
        
        return LLMResponse(
            response=response.text,
            status="success"
        )
        
    except Exception as e:
        print(f"DEBUG: LLM query error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM query failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
