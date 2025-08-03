from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

app1 = FastAPI()

@app1.get("/", response_class=HTMLResponse)
async def serve_homepage():
    return FileResponse("index.html")

app1.mount("/", StaticFiles(directory="."), name="static")

@app1.get("/script.js")
async def serve_javascript():
    return FileResponse("script.js")

@app1.get("/styles.css")
async def serve_styles():
    return FileResponse("styles.css")
