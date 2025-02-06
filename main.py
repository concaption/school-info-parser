"""
path: main.py
author: concaption
description: This script contains the main process that uses the PDFProcessor class to extract information from a PDF file.
It is a cli comand that when given a pdf file or a directory containing pdf files, it will extract the information from the pdf files and save the results in a json files.
"""
from fastapi import FastAPI, UploadFile, File
import os
import json
from src.parser import PDFProcessor
from dotenv import load_dotenv
from src.logger import setup_logging
from typing import List

# Initialize FastAPI app
app = FastAPI()

# Initialize logger
logger = setup_logging()

# Load environment variables
load_dotenv()

# Set API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OpenAI API key not found")


def process_pdf(file_path: str):
    """Process a single PDF file and return extracted data."""
    try:
        logger.info(f"Processing PDF file: {file_path}")
        processor = PDFProcessor(api_key=OPENAI_API_KEY)
        result = processor.process_pdf(file_path)
        output_file = f"data/output_files/{os.path.basename(file_path).replace('.pdf', '_output.json')}"
        if result:
            with open(output_file, "w") as f:
                logger.info(f"Saving results to {output_file}")
                json.dump(result, f, indent=2)
            return result
        else:
            logger.warning("No information extracted from the PDF file")
            return {"message": "No information extracted"}
    except Exception as e:
        logger.error(f"Failed to process PDF file: {str(e)}")
        return {"error": str(e)}


@app.post("/upload-pdf/")
async def upload_pdf(file: UploadFile = File(...)):
    """Endpoint to upload a PDF file and process it."""
    try:
        os.makedirs("temp", exist_ok=True)  # Ensure the temp directory exists
        file_location = f"temp/{file.filename}"
        with open(file_location, "wb") as f:
            f.write(await file.read())
        
        result = process_pdf(file_location)
        return {"filename": file.filename, "result": result}
    except Exception as e:
        return {"error": str(e)}


@app.post("/process-dir/")
async def process_directory(dir_path: str):
    """Endpoint to process all PDFs in a directory."""
    if not os.path.isdir(dir_path):
        return {"error": "Invalid directory path"}
    
    results = []
    for file in os.listdir(dir_path):
        if file.endswith(".pdf"):
            file_path = os.path.join(dir_path, file)
            result = process_pdf(file_path)
            results.append({"file": file, "result": result})

    return {"processed_files": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)