# Notion Document: PDF Data Extraction Enhancements

## Challenges and Techniques

### PDF Structure and Data Extraction
- **Challenge:** PDFs vary significantly in layout, with inconsistent placement of information (multiple locations per page, single location spanning pages). This makes consistent data extraction difficult. Some pages lack complete or structured information.
- **Technique:** Single-page processing with OpenAI API, using a retry mechanism for incomplete extractions.

### API Limitations and Iterative Refinement
- **Challenge:** Initial tests with Anthropic Claude, DeepSeek, Gemini APIs, and RAG techniques did not provide perfect solutions for diverse PDF formats.
- **Technique:** Implemented a loop to re-send page images with previous outputs until satisfactory JSON is achieved. Merging results consolidates scattered data.

### Prompt Engineering and Logging
- **Technique:** Iterative prompts include previous outputs to refine responses ("Do not repeat..."). Detailed logs track processing, API responses, and retries.

## Experiments and Observations
- **Experiment Duration:** Extensive refinement over the past week. The iterative approach has yielded more reliable JSON outputs despite initial unstructured output and blockers.
- **Results & Next Steps:** Overall accuracy is promising, though some pages require multiple retries or provide no course information. Future work includes:
  - Thorough testing across varied PDFs.
  - Finalizing the extracted output structure.
  - Integrating course name, location, and WordPress link into the final output.
  - Automating the entire process with further OpenAI API refinements.

## Technical Implementations and Improvements

### 1. Iterative Prompting and Retry Logic
- **Implementation:** PDFParser appends previous API outputs to prompts for incomplete results. A retry mechanism re-sends the page image until complete JSON is returned.
- **Impact:** Ensures complete data extraction, increasing consistency and accuracy.

### 2. Efficient Image Handling
- **Implementation:** PDF pages are converted to JPEG images using PyMuPDF and encoded in Base64 for OpenAI API requests.
- **Impact:** Improves data transmission quality and reduces format-related errors.

### 3. Merging of Results
- **Implementation:** Results from multiple pages are merged using helper functions in PDFProcessor, filtering duplicates and combining partial data with safe-get methods.
- **Impact:** Aggregates scattered data into a cohesive final JSON output, enhancing reliability.

### 4. Enhanced Logging and Debugging
- **Implementation:** Integration of colorlog provides colored console output and file logging. Detailed logs capture every step.
- **Impact:** Simplifies tracking, debugging, and diagnosing issues, providing clear insights into the processing flow.

### 5. Docker and Environment Variable Integration
- **Implementation:** Dockerfile uses build arguments and runtime environment variables (via .env and Docker Compose) to configure settings.
- **Impact:** Streamlines environment setup, enhances security, and provides flexibility by avoiding hard-coded configurations.

## Future Directions
- **Refine Retry Logic:** Fine-tune retry intervals and thresholds based on real-world testing data.
- **Explore API Enhancements:** Consider integrating additional APIs or refining prompts to capture more nuanced data.
- **Monitor Edge Cases:** Continuously monitor logging outputs to uncover additional edge cases and improve the extraction process.

## Final Thoughts
The current strategy using iterative prompts and retries has significantly improved extraction accuracy. Further tests will continue to refine and automate the aggregation of course information.
