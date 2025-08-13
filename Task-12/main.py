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
import logging
import traceback
import asyncio
from io import BytesIO

import assemblyai as aai
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

try:
    assemblyai_api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if assemblyai_api_key:
        aai.settings.api_key = assemblyai_api_key
        logger.info("AssemblyAI API key loaded successfully")
    else:
        logger.warning("AssemblyAI API key not found - speech transcription will fail")
except Exception as e:
    logger.error(f"Error configuring AssemblyAI: {e}")

try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        logger.info("Gemini API key loaded successfully")
    else:
        logger.warning("Gemini API key not found - LLM responses will fail")
        gemini_api_key = None
except Exception as e:
    logger.error(f"Error configuring Gemini API: {e}")
    gemini_api_key = None

app = FastAPI(
    title="Murf TTS API, Audio Uploader, and LLM Integration",
    description="Text-to-Speech API using Murf AI, audio upload functionality, and LLM integration with Google Gemini.",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory chat history store - using global dictionary
# This is a simple datastore as requested for the prototype
chat_history_store: Dict[str, List[Dict]] = {}

# Fallback responses for error scenarios
FALLBACK_RESPONSES = {
    "stt_error": "I'm sorry, I'm having trouble understanding your audio right now. Please try speaking again or check your microphone.",
    "llm_error": "I'm having trouble connecting to my AI brain right now. Please try again in a moment.",
    "tts_error": "I understand you, but I'm having trouble generating speech right now.",
    "general_error": "I'm experiencing some technical difficulties. Please try again in a moment.",
    "no_speech": "I didn't hear anything. Could you please speak louder or closer to your microphone?",
    "api_key_missing": "The service is temporarily unavailable due to configuration issues. Please try again later."
}

async def generate_fallback_audio(message: str) -> dict:
    """
    Generate fallback TTS audio when Murf API fails
    Returns a mock response structure for consistency
    """
    logger.info(f"Generating fallback response: {message}")
    
    # Try to generate audio for the error message using TTS if available
    error_audio_url = None
    try:
        murf_api_key = os.getenv("MURF_API_KEY")
        if murf_api_key:
            murf_api_key = murf_api_key.strip('"\'')
            headers = {
                "api-key": murf_api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "text": message,
                "voiceId": "en-US-natalie",
                "format": "MP3",
                "sampleRate": 44100
            }
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    "https://api.murf.ai/v1/speech/generate",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    error_audio_url = result.get("audioFile")
                    logger.info("Successfully generated error message audio")
                    
    except Exception as e:
        logger.warning(f"Could not generate audio for error message: {e}")
    
    return {
        "transcription": "System Error",
        "llm_response": message,
        "audio_url": error_audio_url,  # Audio URL if successfully generated
        "message_count": 0,
        "status": "fallback",
        "fallback_text": message,
        "error_audio": True  # Flag to indicate this is an error message
    }

def validate_api_keys() -> dict:
    """
    Validate all required API keys and return status
    """
    status = {
        "assemblyai": bool(os.getenv("ASSEMBLYAI_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "murf": bool(os.getenv("MURF_API_KEY"))
    }
    return status

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

@app.get("/health")
async def health_check():
    """
    Health check endpoint with API key validation
    """
    api_status = validate_api_keys()
    
    return {
        "status": "healthy" if any(api_status.values()) else "degraded",
        "services": {
            "speech_to_text": "available" if api_status["assemblyai"] else "unavailable",
            "llm": "available" if api_status["gemini"] else "unavailable", 
            "text_to_speech": "available" if api_status["murf"] else "unavailable"
        },
        "message": "All services operational" if all(api_status.values()) else "Some services may have limited functionality"
    }

@app.post("/generate-error-audio")
async def generate_error_audio(request: dict):
    """
    Generate audio for error messages
    """
    try:
        error_message = request.get("message", "An error occurred")
        
        murf_api_key = os.getenv("MURF_API_KEY")
        if not murf_api_key:
            return {"audio_url": None, "status": "unavailable", "message": "TTS service unavailable"}
        
        murf_api_key = murf_api_key.strip('"\'')
        
        headers = {
            "api-key": murf_api_key,
            "Content-Type": "application/json"
        }
        
        # Use a more serious/calm voice tone for error messages
        payload = {
            "text": error_message,
            "voiceId": "en-US-ken",  # Different voice for error messages
            "format": "MP3",
            "sampleRate": 44100
        }
        
        logger.info(f"Generating error audio for: {error_message}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.murf.ai/v1/speech/generate",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "audio_url": result.get("audioFile"),
                    "status": "success",
                    "message": "Error audio generated successfully"
                }
            else:
                logger.error(f"Error audio generation failed: {response.status_code}")
                return {"audio_url": None, "status": "failed", "message": "Could not generate error audio"}
                
    except Exception as e:
        logger.error(f"Error in generate_error_audio: {str(e)}")
        return {"audio_url": None, "status": "error", "message": str(e)}

@app.post("/transcribe/file")
async def transcribe_file(file: UploadFile = File(...)):
    """
    Enhanced transcription endpoint with comprehensive error handling
    """
    try:
        # Validate API key
        if not os.getenv("ASSEMBLYAI_API_KEY"):
            logger.error("AssemblyAI API key missing")
            raise HTTPException(
                status_code=503, 
                detail={
                    "error": "Speech recognition service unavailable",
                    "fallback": FALLBACK_RESPONSES["api_key_missing"]
                }
            )
        
        # Validate file
        if not file.filename or not file.size:
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "Invalid audio file",
                    "fallback": "Please upload a valid audio file"
                }
            )
        
        # Check file size (limit to 50MB)
        if file.size > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": "File too large",
                    "fallback": "Please upload a smaller audio file (max 50MB)"
                }
            )
        
        # Attempt transcription with timeout
        config = aai.TranscriptionConfig(
            speech_model=aai.SpeechModel.best,
            language_detection=True
        )
        transcriber = aai.Transcriber(config=config)
        
        # Add timeout for transcription
        try:
            transcript = await asyncio.wait_for(
                asyncio.to_thread(transcriber.transcribe, file.file),
                timeout=60.0  # 60 second timeout
            )
        except asyncio.TimeoutError:
            logger.error("Transcription timeout")
            raise HTTPException(
                status_code=408,
                detail={
                    "error": "Transcription timeout",
                    "fallback": "The audio file is taking too long to process. Please try with a shorter recording."
                }
            )

        if transcript.status == aai.TranscriptStatus.error:
            logger.error(f"AssemblyAI transcription error: {transcript.error}")
            raise HTTPException(
                status_code=500, 
                detail={
                    "error": f"Transcription failed: {transcript.error}",
                    "fallback": FALLBACK_RESPONSES["stt_error"]
                }
            )

        # Check if transcription is empty
        if not transcript.text or not transcript.text.strip():
            logger.warning("Empty transcription result")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "No speech detected",
                    "fallback": FALLBACK_RESPONSES["no_speech"]
                }
            )

        logger.info(f"Transcription successful: {len(transcript.text)} characters")
        return JSONResponse(content={
            "transcription": transcript.text,
            "status": "success"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in transcription: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail={
                "error": f"Transcription service error: {str(e)}",
                "fallback": FALLBACK_RESPONSES["stt_error"]
            }
        )


@app.post("/tts/echo")
async def tts_echo(file: UploadFile = File(...)):
    """
    Enhanced echo bot endpoint with comprehensive error handling
    """
    try:
        logger.info("Starting echo bot processing")
        
        # Step 1: Transcribe the audio using AssemblyAI with error handling
        try:
            if not os.getenv("ASSEMBLYAI_API_KEY"):
                logger.error("AssemblyAI API key missing for echo")
                return await generate_fallback_audio(FALLBACK_RESPONSES["api_key_missing"])
            
            config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best)
            transcriber = aai.Transcriber(config=config)
            
            # Add timeout for transcription
            transcript = await asyncio.wait_for(
                asyncio.to_thread(transcriber.transcribe, file.file),
                timeout=45.0
            )
            
            if transcript.status == aai.TranscriptStatus.error:
                logger.error(f"Echo transcription error: {transcript.error}")
                return await generate_fallback_audio(FALLBACK_RESPONSES["stt_error"])

            transcribed_text = transcript.text
            if not transcribed_text or transcribed_text.strip() == "":
                logger.warning("Echo: No speech detected")
                return await generate_fallback_audio(FALLBACK_RESPONSES["no_speech"])
                
        except asyncio.TimeoutError:
            logger.error("Echo transcription timeout")
            return await generate_fallback_audio("Your audio is taking too long to process. Please try with a shorter recording.")
        except Exception as e:
            logger.error(f"Echo transcription error: {str(e)}")
            return await generate_fallback_audio(FALLBACK_RESPONSES["stt_error"])

        # Step 2: Generate speech using Murf AI with error handling
        try:
            murf_api_key = os.getenv("MURF_API_KEY")
            
            if not murf_api_key:
                logger.error("Murf API key missing for echo")
                return {
                    "transcription": transcribed_text,
                    "llm_response": transcribed_text,  # Echo the transcription
                    "audio_url": None,
                    "status": "partial_success",
                    "message": "Text transcribed successfully, but audio generation is unavailable",
                    "fallback_text": f"I heard you say: '{transcribed_text}', but I can't generate audio right now."
                }
            
            murf_api_key = murf_api_key.strip('"\'')
            
            headers = {
                "api-key": murf_api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "text": transcribed_text,
                "voiceId": "en-US-natalie",
                "format": "MP3",
                "sampleRate": 44100
            }
            
            logger.info(f"Echo - Sending to Murf API: {len(transcribed_text)} characters")
            
            # Add timeout for Murf API call
            async with httpx.AsyncClient(timeout=30.0) as client:
                murf_response = await client.post(
                    "https://api.murf.ai/v1/speech/generate",
                    headers=headers,
                    json=payload
                )
                
                if murf_response.status_code == 200:
                    audio_data = murf_response.json()
                    logger.info("Echo - Murf API success")
                    return JSONResponse(content={
                        "transcription": transcribed_text,
                        "llm_response": transcribed_text,
                        "audio_url": audio_data.get("audioFile"),
                        "status": "success"
                    })
                else:
                    logger.error(f"Echo - Murf API error: {murf_response.status_code} - {murf_response.text}")
                    return {
                        "transcription": transcribed_text,
                        "llm_response": transcribed_text,
                        "audio_url": None,
                        "status": "partial_success",
                        "message": "Text processed but audio generation failed",
                        "fallback_text": f"I heard: '{transcribed_text}' (audio generation temporarily unavailable)"
                    }
                    
        except httpx.TimeoutException:
            logger.error("Echo - Murf API timeout")
            return {
                "transcription": transcribed_text,
                "llm_response": transcribed_text,
                "audio_url": None,
                "status": "partial_success",
                "message": "Audio generation timed out",
                "fallback_text": f"I heard: '{transcribed_text}' but audio generation is taking too long."
            }
        except Exception as e:
            logger.error(f"Echo - Murf API error: {str(e)}")
            return {
                "transcription": transcribed_text,
                "llm_response": transcribed_text,
                "audio_url": None,
                "status": "partial_success",
                "message": "Audio generation failed",
                "fallback_text": f"I heard: '{transcribed_text}' but can't generate audio right now."
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Echo endpoint unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return await generate_fallback_audio(FALLBACK_RESPONSES["general_error"])


@app.post("/generate-audio", response_model=TTSResponse)
async def generate_audio(request: TTSRequest):
    """
    Enhanced TTS endpoint with comprehensive error handling
    """
    try:
        # Validate inputs
        if not request.text or not request.text.strip():
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "Empty text provided",
                    "fallback": "Please provide some text to convert to speech"
                }
            )
        
        if len(request.text) > 5000:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": "Text too long",
                    "fallback": "Please provide shorter text (max 5000 characters)"
                }
            )
        
        # Check API key
        murf_api_key = os.getenv("MURF_API_KEY")
        
        if not murf_api_key:
            logger.error("Murf API key missing for TTS")
            raise HTTPException(
                status_code=503, 
                detail={
                    "error": "Text-to-speech service unavailable", 
                    "fallback": FALLBACK_RESPONSES["api_key_missing"]
                }
            )
        
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
        
        logger.info(f"Generating TTS for {len(request.text)} characters with voice {request.voice_id}")
        
        try:
            # Add timeout for TTS generation
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    "https://api.murf.ai/v1/speech/generate",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info("TTS generation successful")
                    return TTSResponse(
                        audio_url=result.get("audioFile", ""),
                        status="success"
                    )
                elif response.status_code == 401:
                    logger.error("TTS authentication failed")
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "error": "Authentication failed",
                            "fallback": "The text-to-speech service is currently unavailable due to authentication issues"
                        }
                    )
                elif response.status_code == 429:
                    logger.error("TTS rate limit exceeded")
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "Rate limit exceeded",
                            "fallback": "Too many requests. Please wait a moment and try again."
                        }
                    )
                else:
                    logger.error(f"TTS API error: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "error": f"TTS service error: {response.status_code}",
                            "fallback": FALLBACK_RESPONSES["tts_error"]
                        }
                    )
                    
        except httpx.TimeoutException:
            logger.error("TTS request timeout")
            raise HTTPException(
                status_code=408,
                detail={
                    "error": "Request timeout",
                    "fallback": "Audio generation is taking too long. Please try again with shorter text."
                }
            )
        except httpx.RequestError as e:
            logger.error(f"TTS request error: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Network error",
                    "fallback": "Unable to connect to the text-to-speech service. Please check your connection and try again."
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Unexpected error: {str(e)}",
                "fallback": FALLBACK_RESPONSES["tts_error"]
            }
        )

@app.post("/agent/chat/{session_id}")
async def agent_chat_with_history(session_id: str, file: UploadFile = File(...)):
    """
    Enhanced conversational pipeline with comprehensive error handling and fallbacks
    """
    try:
        logger.info(f"Starting chat agent processing for session {session_id}")
        
        # Step 1: Transcribe the audio with error handling
        transcribed_text = ""
        try:
            if not os.getenv("ASSEMBLYAI_API_KEY"):
                logger.error("AssemblyAI API key missing for chat")
                return await generate_fallback_audio(FALLBACK_RESPONSES["api_key_missing"])
            
            config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best)
            transcriber = aai.Transcriber(config=config)
            
            # Add timeout for transcription
            transcript = await asyncio.wait_for(
                asyncio.to_thread(transcriber.transcribe, file.file),
                timeout=45.0
            )
            
            if transcript.status == aai.TranscriptStatus.error:
                logger.error(f"Chat transcription error: {transcript.error}")
                return await generate_fallback_audio(FALLBACK_RESPONSES["stt_error"])

            transcribed_text = transcript.text
            if not transcribed_text or transcribed_text.strip() == "":
                logger.warning("Chat: No speech detected")
                return await generate_fallback_audio(FALLBACK_RESPONSES["no_speech"])
                
        except asyncio.TimeoutError:
            logger.error("Chat transcription timeout")
            return await generate_fallback_audio("Your audio is taking too long to process. Please try with a shorter recording.")
        except Exception as e:
            logger.error(f"Chat transcription error: {str(e)}")
            return await generate_fallback_audio(FALLBACK_RESPONSES["stt_error"])

        logger.info(f"Chat Agent - Session {session_id} - Transcribed: {len(transcribed_text)} chars")

        # Step 2: Get chat history and add user message
        chat_history = get_chat_history(session_id)
        add_message_to_history(session_id, "user", transcribed_text)

        # Step 3: Generate LLM response with error handling
        llm_text = ""
        try:
            if not gemini_api_key:
                logger.error("Gemini API key missing for chat")
                llm_text = FALLBACK_RESPONSES["llm_error"]
            else:
                # Build conversation context
                conversation_context = "You are a helpful AI assistant. Please respond in a conversational and concise manner (keep it under 2500 characters to fit TTS limits).\n\nConversation history:\n"
                
                # Include recent conversation history
                recent_history = chat_history[-10:] if len(chat_history) > 10 else chat_history
                for message in recent_history:
                    if message["role"] == "user":
                        conversation_context += f"User: {message['content']}\n"
                    else:
                        conversation_context += f"Assistant: {message['content']}\n"
                
                conversation_context += f"User: {transcribed_text}\n\nPlease respond to the user's latest message."

                # Query LLM with timeout
                model = genai.GenerativeModel('gemini-1.5-flash')
                llm_response = await asyncio.wait_for(
                    asyncio.to_thread(model.generate_content, conversation_context),
                    timeout=30.0
                )
                
                if not llm_response.text:
                    logger.error("Empty LLM response")
                    llm_text = FALLBACK_RESPONSES["llm_error"]
                else:
                    llm_text = llm_response.text.strip()
                    
                    # Truncate if too long
                    if len(llm_text) > 3000:
                        llm_text = llm_text[:2900] + "... I have more to share, but let me pause here."
                
        except asyncio.TimeoutError:
            logger.error("LLM response timeout")
            llm_text = "I'm taking a bit longer to think. Let me give you a quick response for now."
        except Exception as e:
            logger.error(f"Chat LLM error: {str(e)}")
            llm_text = FALLBACK_RESPONSES["llm_error"]

        # Add assistant message to history
        add_message_to_history(session_id, "assistant", llm_text)
        message_count = get_session_message_count(session_id)

        logger.info(f"Chat Agent - Session {session_id} - Generated response: {len(llm_text)} chars")

        # Step 4: Generate speech with error handling
        try:
            murf_api_key = os.getenv("MURF_API_KEY")
            
            if not murf_api_key:
                logger.error("Murf API key missing for chat")
                return {
                    "transcription": transcribed_text,
                    "llm_response": llm_text,
                    "audio_url": None,
                    "session_id": session_id,
                    "message_count": message_count,
                    "status": "partial_success",
                    "message": "Conversation processed but audio generation unavailable",
                    "fallback_text": f"Your message: '{transcribed_text}'. My response: '{llm_text}' (Audio generation temporarily unavailable)"
                }
            
            murf_api_key = murf_api_key.strip('"\'')
            
            headers = {
                "api-key": murf_api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "text": llm_text,
                "voiceId": "en-US-natalie",
                "format": "MP3",
                "sampleRate": 44100
            }
            
            logger.info(f"Chat - Session {session_id} - Sending to Murf API")
            
            # Add timeout for Murf API call
            async with httpx.AsyncClient(timeout=30.0) as client:
                murf_response = await client.post(
                    "https://api.murf.ai/v1/speech/generate",
                    headers=headers,
                    json=payload
                )
                
                if murf_response.status_code == 200:
                    audio_data = murf_response.json()
                    logger.info(f"Chat - Session {session_id} - Murf API success")
                    return JSONResponse(content={
                        "transcription": transcribed_text,
                        "llm_response": llm_text,
                        "audio_url": audio_data.get("audioFile"),
                        "session_id": session_id,
                        "message_count": message_count,
                        "status": "success"
                    })
                else:
                    logger.error(f"Chat - Murf API error: {murf_response.status_code} - {murf_response.text}")
                    return {
                        "transcription": transcribed_text,
                        "llm_response": llm_text,
                        "audio_url": None,
                        "session_id": session_id,
                        "message_count": message_count,
                        "status": "partial_success",
                        "message": "Conversation processed but audio generation failed",
                        "fallback_text": f"Your message: '{transcribed_text}'. My response: '{llm_text}' (Audio generation failed)"
                    }
                    
        except httpx.TimeoutException:
            logger.error(f"Chat - Session {session_id} - Murf API timeout")
            return {
                "transcription": transcribed_text,
                "llm_response": llm_text,
                "audio_url": None,
                "session_id": session_id,
                "message_count": message_count,
                "status": "partial_success",
                "message": "Audio generation timed out",
                "fallback_text": f"Your message: '{transcribed_text}'. My response: '{llm_text}' (Audio generation taking too long)"
            }
        except Exception as e:
            logger.error(f"Chat - Session {session_id} - Murf API error: {str(e)}")
            return {
                "transcription": transcribed_text,
                "llm_response": llm_text,
                "audio_url": None,
                "session_id": session_id,
                "message_count": message_count,
                "status": "partial_success",
                "message": "Audio generation failed",
                "fallback_text": f"Your message: '{transcribed_text}'. My response: '{llm_text}' (Audio generation temporarily unavailable)"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat agent unexpected error for session {session_id}: {str(e)}")
        logger.error(traceback.format_exc())
        return await generate_fallback_audio(FALLBACK_RESPONSES["general_error"])


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
