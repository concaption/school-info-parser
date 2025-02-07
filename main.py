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
import tempfile
import httpx
import redis.asyncio as redis


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

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=6379,
    password=os.getenv("REDIS_PASSWORD"),
    db=0,
    decode_responses=True
)


# Reuse existing pdf processing function for background tasks
async def process_pdf(file_data: dict) -> Optional[dict]:
    try:
        logger.info(f"Processing PDF file: {file_data['filename']}")
        content = file_data["content"]
        # Write the content to a temporary file in binary mode
        with tempfile.NamedTemporaryFile(delete=False, mode="w+b") as temp_file:
            temp_file.write(content)
            temp_file.flush()
            temp_file_path = temp_file.name

        processor = PDFProcessor(api_key=OPENAI_API_KEY)
        result = processor.process_pdf(temp_file_path)
        # Clean up the temporary file
        os.unlink(temp_file_path)

        if result:
            return result
        else:
            logger.warning("No information extracted from the PDF file")
            return None
    except Exception as e:
        logger.error(f"Failed to process PDF file: {str(e)}")
        return None


# Background job processor
async def process_job(job_id: str, files_data: list, callback_url: Optional[str]):
    results = []
    for file_data in files_data:
        res = await process_pdf(file_data)
        if res:
            results.append({file_data["filename"]: res})
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
    callback_url: Optional[str] = Query(None, description="Optional callback URL"),
):
    """Submits a job to process PDFs asynchronously."""
    if not files:
        raise HTTPException(status_code=400, detail="No PDF files uploaded")
    job_id = str(uuid.uuid4())
    # Read each file's content and prepare a list of file data dictionaries
    files_data = []
    for file in files:
        file_content = await file.read()
        files_data.append({"filename": file.filename, "content": file_content})
    # Save initial job status
    job_data = {"status": "processing", "results": None}
    await redis_client.set(job_id, json.dumps(job_data))
    background_tasks.add_task(process_job, job_id, files_data, callback_url)
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
