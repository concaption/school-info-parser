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
import traceback
from src.csv_converter import json_to_dataframe, dataframe_to_csv_string, json_to_csv

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

app = FastAPI(title="School Prospectus Processor", version="0.1.0")

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
    
    if status == "completed":
        try:
            logger.info(f"Job {job_id} completed successfully, generating CSV data")
            for result_idx, result_entry in enumerate(results):
                logger.info(f"Processing result {result_idx+1}/{len(results)}")
                for filename, result_data in result_entry.items():
                    logger.info(f"Generating CSV for file: {filename}")
                    if "merged_results" in result_data:
                        try:
                            logger.debug("Converting to DataFrame")
                            if result_data["merged_results"] and isinstance(result_data["merged_results"], dict):
                                logger.debug(f"School name in merged_results: {result_data['merged_results'].get('name', 'Not found')}")
                            else:
                                logger.warning("merged_results is empty or not a dictionary")
                            
                            df = json_to_dataframe(result_data)
                            if not df.empty:
                                logger.debug(f"DataFrame created with {len(df)} rows, converting to CSV")
                                csv_data = dataframe_to_csv_string(df)
                                logger.debug(f"CSV string created, length: {len(csv_data)}")
                                
                                if csv_data:
                                    logger.debug(f"Storing CSV data in Redis with key: {job_id}_csv_{filename}")
                                    await redis_client.set(f"{job_id}_csv_{filename}", csv_data)
                                    logger.info(f"CSV data for {filename} stored in Redis")
                                else:
                                    logger.error(f"Failed to generate CSV string for {filename}")
                            else:
                                logger.warning(f"Empty DataFrame for {filename}, no CSV generated")
                        except Exception as e:
                            logger.error(f"Error generating CSV for {filename}: {str(e)}")
                            logger.debug(traceback.format_exc())
                    else:
                        logger.warning(f"No merged_results found for {filename}, skipping CSV generation")
        except Exception as e:
            logger.error(f"Failed to create CSV data: {str(e)}")
            logger.debug(traceback.format_exc())
    
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
    return {"job_id": job_id, "status": "processing"}


@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Returns the status or results of a submitted job."""
    data = await redis_client.get(job_id)
    if not data:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=json.loads(data))


@app.get("/job/{job_id}/csv")
async def get_job_csv(job_id: str, filename: Optional[str] = None):
    try:
        logger.info(f"CSV request for job {job_id}, filename: {filename}")
        job_data_str = await redis_client.get(job_id)
        if not job_data_str:
            logger.warning(f"Job {job_id} not found")
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_data = json.loads(job_data_str)
        if job_data.get("status") != "completed":
            logger.warning(f"Job {job_id} not completed yet, status: {job_data.get('status')}")
            raise HTTPException(status_code=400, detail="Job not completed yet")
        
        results = job_data.get("results", [])
        if not results:
            logger.warning(f"No results found for job {job_id}")
            raise HTTPException(status_code=404, detail="No results found for this job")
        
        if filename:
            logger.info(f"Looking for CSV data for specific file: {filename}")
            csv_data = await redis_client.get(f"{job_id}_csv_{filename}")
            if not csv_data:
                logger.warning(f"CSV for file {filename} not found in job {job_id}")
                raise HTTPException(status_code=404, detail=f"CSV for file {filename} not found")
        else:
            logger.info("No filename specified, using first file in results")
            first_file_entry = results[0]
            first_filename = next(iter(first_file_entry))
            logger.info(f"Using first file: {first_filename}")
            
            csv_data = await redis_client.get(f"{job_id}_csv_{first_filename}")
            if not csv_data:
                logger.warning(f"CSV data for {first_filename} not found in Redis, attempting to generate on-the-fly")
                try:
                    first_result = first_file_entry[first_filename]
                    df = json_to_dataframe(first_result)
                    if df.empty:
                        logger.error("Generated DataFrame is empty")
                        raise HTTPException(status_code=404, detail="Could not generate CSV data")
                    
                    csv_data = dataframe_to_csv_string(df)
                    if not csv_data:
                        logger.error("Generated CSV string is empty")
                        raise HTTPException(status_code=500, detail="Generated empty CSV data")
                    
                    logger.info(f"Storing generated CSV data in Redis for {first_filename}")
                    await redis_client.set(f"{job_id}_csv_{first_filename}", csv_data)
                except Exception as e:
                    logger.error(f"Error generating CSV on-the-fly: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Error generating CSV: {str(e)}")
        
        return Response(content=csv_data, media_type="text/csv", headers={
            "Content-Disposition": f"attachment; filename=school_data_{job_id}.csv"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving CSV: {str(e)}")
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error retrieving CSV: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
