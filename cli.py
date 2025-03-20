"""
path: cli.py
author: concaption
description: This script contains the main entry point for the CLI application.
It is a cli comand that when given a pdf file or a directory containing pdf files, it will extract the information from the pdf files and save the results in a json files.
"""
import os
import json
from src.parser import PDFProcessor
from dotenv import load_dotenv
from src.logger import setup_logging
import click
from src.utils import melt_results, export_to_excel


# Initialize logger
logger = setup_logging()

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OpenAI API key not found")


def process_pdf(file_path, generate_excel=False):
    try:
        logger.info(f"Processing PDF file: {file_path}")
        processor = PDFProcessor(api_key=OPENAI_API_KEY)
        result = processor.process_pdf(file_path)
        
        # Ensure output directories exist
        os.makedirs("data/output_files", exist_ok=True)
        
        # Base filename without extension
        base_filename = os.path.basename(file_path).replace('.pdf', '')
        output_file = f"data/output_files/{base_filename}_output.json"
        
        if result:
            # Save JSON output
            with open(output_file, "w") as f:
                logger.info(f"Saving JSON results to {output_file}")
                json.dump(result, f, indent=2)
                
            # Generate Excel file if requested
            if generate_excel and "merged_results" in result:
                logger.info("Generating Excel file from merged results")
                try:
                    melted_data = melt_results(result["merged_results"])
                    if melted_data:
                        excel_dir = "data/output_files"
                        excel_path = export_to_excel(melted_data, excel_dir)
                        if excel_path:
                            # Rename the excel file to match our base filename
                            new_excel_path = os.path.join(excel_dir, f"{base_filename}_output.xlsx")
                            if os.path.exists(new_excel_path):
                                os.remove(new_excel_path)
                            os.rename(excel_path, new_excel_path)
                            logger.info(f"Excel file saved to {new_excel_path}")
                        else:
                            logger.warning("Failed to generate Excel file")
                    else:
                        logger.warning("No data to export to Excel")
                except Exception as e:
                    logger.error(f"Error generating Excel file: {str(e)}")
            
            return result
        else:
            logger.warning("No information extracted from the PDF file")
            return None

    except Exception as e:
        logger.error(f"Failed to process PDF file: {str(e)}")
        raise

def process_dir(dir_path, generate_excel=False):
    try:
        logger.info(f"Processing PDF files in directory: {dir_path}")
        results = []
        for file in os.listdir(dir_path):
            if file.endswith(".pdf"):
                file_path = os.path.join(dir_path, file)
                result = process_pdf(file_path, generate_excel)
                if result:
                    results.append({"filename": file, "result": result})
        return results
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
@click.option('--excel/--no-excel', default=False, help='Generate Excel output file')
def process(file_path, dir_path, excel):
    try:
        if not file_path and not dir_path:
            logger.error("Please provide either a file path or a directory path")
            return
        if file_path:
            process_pdf(file_path, generate_excel=excel)
        elif dir_path:
            process_dir(dir_path, generate_excel=excel)
    except Exception as e:
        logger.error(f"Main process failed: {str(e)}")
        raise

if __name__ == "__main__":
    cli()