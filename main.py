#!/usr/bin/env python

import os
import base64
import json
import fitz  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv
import io
from PIL import Image
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import logging
from logging.handlers import RotatingFileHandler
import sys
import traceback


# Set up logging
def setup_logging():
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Configure logging
    logger = logging.getLogger("PDFParser")
    logger.setLevel(logging.DEBUG)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        "logs/pdf_parser.log", maxBytes=1024 * 1024, backupCount=5  # 1MB
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create formatters and add it to the handlers
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")

    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Initialize logger
logger = setup_logging()

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OpenAI API key not found")


class Price(BaseModel):
    duration: str = Field(..., description="Duration of the course")
    price: str = Field(..., description="Price of the course")
    currency: str = Field(..., description="Currency of the price")

class Course(BaseModel):
    name: str = Field(..., description="Name of the course")
    lessons_per_week: int = Field(..., description="Number of lessons per week")
    description: str = Field(..., description="Course description")
    prices: List[Price] = Field(..., description="List of prices for the course")
    requirements: Optional[str] = Field(None, description="Course requirements")

class Accommodation(BaseModel):
    type: str = Field(..., description="Type of accommodation")
    price_per_week: str = Field(..., description="Weekly price of accommodation")
    description: str = Field(..., description="Accommodation description")
    supplements: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional supplements")

class Location(BaseModel):
    city: str = Field(..., description="City where the school is located")
    country: str = Field(..., description="Country where the school is located")
    address: str = Field(..., description="Address of the school")
    courses: List[Course] = Field(..., description="List of available courses")
    accommodations: List[Accommodation] = Field(..., description="List of accommodations")
    additional_fees: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional fees")

class School(BaseModel):
    name: str = Field(..., description="Name of the school")
    locations: List[Location] = Field(..., description="List of locations where the school operates")
    terms: Optional[Dict[str, str]] = Field(default_factory=dict, description="Terms and conditions")

class PDFParser:
    def __init__(self, api_key):
        logger.info("Initializing PDFParser")

        self.client = OpenAI(api_key=api_key)
        self.system_prompt = """Please analyze this image and extract the language school information. Focus on identifying:
- School name
- Location details
- Course information
- Pricing
- Accommodation options
- Any terms or conditions

Format the response as valid JSON with this structure:
{
    "school_name": "Centre of English Studies",
    "locations": [
        {
            "city": "Dublin",
            "country": "Ireland",
            "address": "...",
            "courses": [
                {
                    "name": "Standard General English",
                    "lessons_per_week": 20,
                    "description": "Morning classes Mon-Fri",
                    "prices": [
                        {"duration": "2-4 weeks", "price": "€355", "currency": "EUR"}
                    ]
                }
            ],
            "accommodations": [
                {
                    "type": "Homestay",
                    "price_per_week": "€280",
                    "description": "Single room, half board",
                    "supplements": {
                        "Summer": "€35/week"
                    }
                }
            ],
            "additional_fees": {
                "registration": "€85"
            }
        }
    ],
    "terms": {
        "cancellation": "14 days notice required"
    }
}"""

    def parse_page(self, pixmap):
        try:
            logger.debug("Converting PyMuPDF pixmap to PIL Image")
            img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

            logger.debug("Converting PIL Image to JPEG bytes")
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="JPEG")
            img_byte_arr = img_byte_arr.getvalue()

            logger.debug("Encoding image to base64")
            base64_image = base64.b64encode(img_byte_arr).decode("utf-8")

            logger.info("Sending request to OpenAI API")
            response = self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-11-20",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.system_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_completion_tokens=16383,
                response_format=School,
            )

            logger.debug("Received response from OpenAI API")

            # Log the raw response content for debugging
            logger.debug(
                f"Raw API response content: {response.choices[0].message.content}"
            )

            try:
                parsed_response = json.loads(response.choices[0].message.content)
                logger.info("Successfully parsed JSON response")
                return parsed_response
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response content: {response.choices[0].message.content}")
                raise

        except Exception as e:
            logger.error(f"Error in parse_page: {str(e)}")
            raise


class PDFProcessor:
    def __init__(self, api_key):
        logger.info("Initializing PDFProcessor")
        self.parser = PDFParser(api_key)
        self.results = []
    
    def process_pdf(self, pdf_path):
        logger.info(f"Processing PDF: {pdf_path}")
        try:
            if not os.path.exists(pdf_path):
                logger.error(f"PDF file not found: {pdf_path}")
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            pdf_document = fitz.open(pdf_path)
            logger.info(f"Opened PDF with {pdf_document.page_count} pages")
            
            for page_num in range(pdf_document.page_count):
                logger.info(f"Processing page {page_num + 1}/{pdf_document.page_count}")
                page = pdf_document[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                
                try:
                    page_data = self.parser.parse_page(pix)
                    self.results.append(page_data)
                    logger.info(f"Successfully processed page {page_num + 1}")
                except Exception as e:
                    logger.error(f"Error processing page {page_num + 1}: {str(e)}")
            
            pdf_document.close()
            logger.info("PDF processing completed")
            # return self.merge_results()
            return self.results
            
        except Exception as e:
            logger.error(f"Error in process_pdf: {str(e)}")
            raise

# Usage Example
if __name__ == "__main__":
    try:
        logger.info("Starting PDF processing")
        processor = PDFProcessor(api_key=OPENAI_API_KEY)
        result = processor.process_pdf("data/input_files/2025_CES_Adult_Price_List_as_at_8th_August.pdf")
        
        output_file = "output.json"
        logger.info(f"Writing results to {output_file}")
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        
        logger.info("Processing complete. Results saved to output.json")
        
    except Exception as e:
        logger.error(f"Main process failed: {str(e)}")
        raise