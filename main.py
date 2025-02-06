"""
path: main.py
author: concaption
description: FastAPI application that asynchronously processes PDF files,
supports background job submission with an optional callback, and exposes a job status endpoint.
"""
import os
import json
import uuid
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv
import httpx

from src.parser import PDFProcessor
from src.logger import setup_logging

# Initialize logger
logger = setup_logging()

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OpenAI API key not found")

app = FastAPI()

# Initialize Redis client using asyncio
import redis.asyncio as redis
redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, decode_responses=True)

# Reuse existing pdf processing function for background tasks
async def process_pdf(file: UploadFile) -> Optional[dict]:
    try:
        logger.info(f"Processing PDF file: {file.filename}")
        processor = PDFProcessor(api_key=OPENAI_API_KEY)
        content = await file.read()
        result = processor.process_pdf(content)
        if result:
            return result
        else:
            logger.warning("No information extracted from the PDF file")
            return None
    except Exception as e:
        logger.error(f"Failed to process PDF file: {str(e)}")
        return None

# Background job processor
async def process_job(job_id: str, files: List[UploadFile], callback_url: Optional[str]):
    results = []
    for file in files:
        res = await process_pdf(file)
        if res:
            results.append({file.filename: res})
    status = "failed" if not results else "completed"
    job_data = {"status": status, "results": results}
    await redis_client.set(job_id, json.dumps(job_data))
    if callback_url:
        async with httpx.AsyncClient() as client:
            try:
                await client.post(callback_url, json=job_data)
            except Exception as e:
                logger.error(f"Callback failed: {str(e)}")

@app.get("/")
def root():
    # Redirect root to docs page
    return RedirectResponse(url="/docs")

@app.post("/submit-job/")
async def submit_job(
    background_tasks: BackgroundTasks,
    files: List[UploadFile],
    callback_url: Optional[str] = Query(None, description="Optional callback URL")
):
    """Submits a job to process PDFs asynchronously."""
    if not files:
        raise HTTPException(status_code=400, detail="No PDF files uploaded")
    job_id = str(uuid.uuid4())
    # Save initial job status
    job_data = {"status": "processing", "results": None}
    await redis_client.set(job_id, json.dumps(job_data))
    background_tasks.add_task(process_job, job_id, files, callback_url)
    return {"job_id": job_id}

@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Returns the status or results of a submitted job."""
    data = await redis_client.get(job_id)
    if not data:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=json.loads(data))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)