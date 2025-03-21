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

from fastapi import FastAPI, Response, UploadFile, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv
import tempfile
import httpx
import redis.asyncio as redis
import traceback
from src.utils import melt_results, export_to_excel
import pandas as pd

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

# Initialize Redis client using asyncio - simple connection that was working fine
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


# Background job processor with immediate updates to Redis
async def process_job(job_id: str, files_data: list, callback_url: Optional[str]):
    results = []
    total_files = len(files_data)
    processed_files = 0
    
    # Update job status with progress information - force immediate update
    async def update_job_status(current_file=None):
        status = "processing" if processed_files < total_files else "completed"
        job_data = {
            "status": status,
            "progress": {
                "processed": processed_files,
                "total": total_files,
                "percentage": round((processed_files / total_files) * 100) if total_files > 0 else 0,
                "current_file": current_file
            },
            "results": results  # Always include current results
        }
        
        try:
            # Force immediate update - this is critical to get real-time progress
            await redis_client.set(job_id, json.dumps(job_data))
            logger.info(f"Job {job_id} status updated: {status}, {processed_files}/{total_files} files processed")
        except Exception as e:
            logger.error(f"Failed to update job status in Redis: {str(e)}")
            
        return job_data
    
    # Must set initial status to "processing" immediately
    await update_job_status()
    
    # Process each file and update status BEFORE and AFTER processing
    for idx, file_data in enumerate(files_data):
        current_file = file_data['filename']
        try:
            # CRITICAL: Update Redis BEFORE starting to process the file
            # This ensures users will see status change immediately
            logger.info(f"Starting to process file {idx + 1}/{total_files}: {current_file}")
            await update_job_status(current_file)
            
            # Process the file - this may take a long time
            res = await process_pdf(file_data)
            
            if res:
                # Add results and update processed count
                results.append({current_file: res})
                logger.info(f"Successfully processed file {current_file}")
            else:
                logger.warning(f"No results for file {current_file}")
            
            # Update processed count even if no results
            processed_files += 1
                
            # Update Redis immediately after processing this file
            await update_job_status()
            
        except Exception as e:
            logger.error(f"Error processing file {current_file}: {str(e)}")
            logger.debug(traceback.format_exc())
            processed_files += 1  # Count as processed even if it failed
            await update_job_status()  # Make sure status is updated
    
    # Final update with completed status
    job_data = await update_job_status()
    
    # Send callback if URL was provided
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
    
    # CRITICAL: Fully initialize the job data with all fields
    # to ensure status endpoint returns properly formatted data immediately
    job_data = {
        "status": "processing", 
        "progress": {
            "processed": 0,
            "total": len(files_data),
            "percentage": 0,
            "current_file": None
        },
        "results": []  # Empty but initialized array
    }
    
    try:
        # Set the initial status in Redis BEFORE starting the background task
        await redis_client.set(job_id, json.dumps(job_data))
        
        # Start background task AFTER setting initial status
        background_tasks.add_task(process_job, job_id, files_data, callback_url)
        return {"job_id": job_id, "status": "processing"}
    except Exception as e:
        logger.error(f"Error submitting job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error submitting job: {str(e)}")


@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Returns the status or results of a submitted job."""
    try:
        # Get job data from Redis
        job_data_str = await redis_client.get(job_id)
        if not job_data_str:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Parse job data
        job_data = json.loads(job_data_str)
        
        # Always return data regardless of status - critical for in-progress reporting
        return JSONResponse(content=job_data)
        
    except Exception as e:
        logger.error(f"Error retrieving job status: {str(e)}")
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error retrieving job status: {str(e)}")


@app.get("/job/{job_id}/xlsx")
async def get_job_xlsx(job_id: str):
    """Returns Excel file containing all processed data for the job so far."""
    try:
        logger.info(f"Excel request for job {job_id}")
        
        # Get job data
        job_data_str = await redis_client.get(job_id)
        if not job_data_str:
            logger.warning(f"Job {job_id} not found")
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_data = json.loads(job_data_str)
        
        # Get results, whether job is completed or still in progress
        results = job_data.get("results", [])
        if not results:
            logger.warning(f"No results found for job {job_id} yet")
            raise HTTPException(status_code=404, detail="No results found for this job yet")
        
        # Generate Excel file on-the-fly, combining ALL results processed so far
        all_melted_data = []
        files_processed = []
        
        # Process all files in job results
        logger.info("Processing all available results from job")
        
        for result_entry in results:
            for file_name, result_data in result_entry.items():
                files_processed.append(file_name)
                if "merged_results" in result_data and result_data["merged_results"]:
                    logger.info(f"Processing merged results for {file_name}")
                    try:
                        # The source_filename should already be in merged_results from the parser
                        # If not, we'll add it here as a fallback
                        if result_data["merged_results"] and isinstance(result_data["merged_results"], dict):
                            if "source_filename" not in result_data["merged_results"]:
                                result_data["merged_results"]["source_filename"] = file_name
                        
                        melted_data = melt_results(result_data["merged_results"])
                        if melted_data:
                            # The source_filename should now be included in each row from melt_results
                            # This is a failsafe to ensure it's there
                            for row in melted_data:
                                if "source_filename" not in row:
                                    row["source_filename"] = file_name
                            
                            all_melted_data.extend(melted_data)
                            logger.info(f"Added {len(melted_data)} rows from {file_name}")
                        else:
                            logger.warning(f"No melted data generated for {file_name}")
                    except Exception as e:
                        logger.error(f"Error melting results for {file_name}: {str(e)}")
                        logger.debug(traceback.format_exc())
                else:
                    logger.warning(f"No merged_results found for {file_name}")
        
        if not all_melted_data:
            logger.error("No data available for Excel generation")
            raise HTTPException(status_code=404, detail="No data available for Excel generation")
        
        # Get the progress information to include in the filename
        progress_info = job_data.get("progress", {})
        processed = progress_info.get("processed", 0)
        total = progress_info.get("total", 0)
        
        # Create status indicator based on job status
        status_indicator = ""
        if job_data.get("status") == "processing":
            status_indicator = f"_IN_PROGRESS_{processed}_of_{total}_"
        
        # Generate a descriptive filename with the files processed so far
        max_files_in_name = 3  # Max number of filenames to include in output filename
        filename_parts = []
        for i, name in enumerate(files_processed):
            if i < max_files_in_name:
                # Get base filename without extension and add to parts
                base_name = os.path.splitext(name)[0]
                filename_parts.append(base_name)
        
        # Create Excel filename
        if filename_parts:
            if len(filename_parts) < len(files_processed):
                # If we truncated the list, add indication of more files
                excel_filename = f"{'-'.join(filename_parts)}_plus_{len(files_processed) - len(filename_parts)}_more{status_indicator}{job_id}.xlsx"
            else:
                excel_filename = f"{'-'.join(filename_parts)}{status_indicator}{job_id}.xlsx"
        else:
            excel_filename = f"school_data{status_indicator}{job_id}.xlsx"
        
        # Ensure the filename doesn't get too long
        if len(excel_filename) > 100:
            excel_filename = f"school_data{status_indicator}{job_id}.xlsx"
        
        # Create DataFrame from all melted data
        df = pd.DataFrame(all_melted_data)
        
        # Write DataFrame to Excel file in memory
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
            excel_path = temp_file.name
            
            # Use ExcelWriter for better formatting
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='School Info', index=False)
                
                # Auto-adjust column widths
                worksheet = writer.sheets['School Info']
                for i, col in enumerate(df.columns):
                    max_width = max(
                        df[col].astype(str).map(len).max() if len(df) > 0 else 0,  # Width of data
                        len(col)  # Width of column header
                    ) + 2  # Add a little extra space
                    
                    # Limit max width to avoid very wide columns
                    max_width = min(max_width, 50)
                    
                    # Excel column widths are measured in characters
                    col_letter = chr(65 + i) if i < 26 else chr(64 + i // 26) + chr(65 + i % 26)
                    worksheet.column_dimensions[col_letter].width = max_width
        
        # Read the generated Excel file
        with open(excel_path, 'rb') as f:
            excel_data = f.read()
        
        # Clean up the temp file
        os.unlink(excel_path)
        
        # Return the Excel file as a response
        logger.info(f"Returning Excel file: {excel_filename}")
        return Response(
            content=excel_data, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            headers={"Content-Disposition": f"attachment; filename=\"{excel_filename}\""}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving Excel: {str(e)}")
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error retrieving Excel: {str(e)}")


# Health check endpoint to verify Redis connection
@app.get("/health")
async def health_check():
    try:
        if await redis_client.ping():
            return {"status": "healthy", "redis": "connected"}
        return {"status": "unhealthy", "redis": "not responding"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "redis": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
