from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
import shutil

import assemblyai as aai

load_dotenv()

aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

app = FastAPI(
    title="Murf TTS API and Audio Uploader",
    description="Text-to-Speech API using Murf AI and audio upload functionality.",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

class TTSRequest(BaseModel):
    text: str
    voice_id: str = "en-US-natalie"

class TTSResponse(BaseModel):
    audio_url: str
    status: str

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
