"""
path: main.py
author: concaption
description: This script contains the main process that uses the PDFProcessor class to extract information from a PDF file.
It is a cli comand that when given a pdf file or a directory containing pdf files, it will extract the information from the pdf files and save the results in a json files.
"""
import os
import json
from src.parser import PDFProcessor
from dotenv import load_dotenv
from src.logger import setup_logging
import click


# Initialize logger
logger = setup_logging()

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OpenAI API key not found")


def process_pdf(file_path):
    try:
        logger.info(f"Processing PDF file: {file_path}")
        processor = PDFProcessor(api_key=OPENAI_API_KEY)
        result = processor.process_pdf(file_path)
        output_file =  f"data/output_files/{os.path.basename(file_path).replace('.pdf', '_output.json')}"
        if result:
            with open(output_file, "w") as f:
                logger.info(f"Saving results to {output_file}")
                json.dump(result, f, indent=2)
        else:
            logger.warning("No information extracted from the PDF file")

    except Exception as e:
        logger.error(f"Failed to process PDF file: {str(e)}")
        raise

def process_dir(dir_path):
    try:
        logger.info(f"Processing PDF files in directory: {dir_path}")
        processor = PDFProcessor(api_key=OPENAI_API_KEY)
        for file in os.listdir(dir_path):
            if file.endswith(".pdf"):
                file_path = os.path.join(dir_path, file)
                process_pdf(file_path)
    except Exception as e:
        logger.error(f"Failed to process PDF files in directory: {str(e)}")
        raise


@click.group()
def cli():
    """Main entry point for the CLI"""
    pass

@cli.command()
@click.option('--file_path', default=None, help='Path to the PDF file to process')
@click.option('--dir_path', default=None, help='Path to the directory containing PDF files to process')
def process(file_path, dir_path):
    try:
        if not file_path and not dir_path:
            logger.error("Please provide either a file path or a directory path")
            return
        if file_path:
            process_pdf(file_path)
        elif dir_path:
            process_dir(dir_path)
    except Exception as e:
        logger.error(f"Main process failed: {str(e)}")
        raise

if __name__ == "__main__":
    cli()