# School Information Parser

A FastAPI application that processes PDF files containing language school information using OpenAI's GPT-4 Vision API. The application extracts structured data about courses, accommodations, and pricing.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/concaption/school-info-parser)

<div>
    <a href="https://www.loom.com/share/d018d31a1bd34387874f94361a5c8ffa">
      <p>School Information Parser - Watch Video</p>
    </a>
    <a href="https://www.loom.com/share/d018d31a1bd34387874f94361a5c8ffa">
      <img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/d018d31a1bd34387874f94361a5c8ffa-f98922728e9badf7-full-play.gif">
    </a>
  </div>

Read [Notion.md](notion.md) for more details. 

## Features

- Asynchronous PDF processing with background jobs
- Redis-based job queue system
- Colored logging with file and console output
- Docker containerization
- Callback support for job completion notifications
- Structured data extraction using Pydantic models
- Automatic API documentation with Swagger UI

## Prerequisites

- Python 3.9+
- Docker and Docker Compose
- OpenAI API key
- Redis server

## Installation

1. Clone the repository:
```bash
git clone https://github.com/concaption/school-info-parser.git
cd school-info-parser
```

2. Create and populate .env file:
```bash
OPENAI_API_KEY=your_api_key_here
REDIS_HOST=redis
```

3. Build and run with Docker Compose:
```bash
docker-compose up --build
```

## API Endpoints

- `GET /` - Redirects to API documentation
- `POST /submit-job/` - Submit PDFs for processing
- `GET /job/{job_id}` - Check job status and results

## Usage

1. Access the API documentation:
```
http://localhost:8000/docs
```

2. Submit a PDF file for processing:
```bash
curl -X POST "http://localhost:8000/submit-job/" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "files=@your_pdf_file.pdf"
```

3. Check job status:
```bash
curl -X GET "http://localhost:8000/job/{job_id}"
```

## Development

1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run tests:
```bash
pytest
```

## Project Structure

```
school-info-parser/
├── src/
│   ├── parser.py      # PDF processing logic
│   ├── schema.py      # Pydantic models
│   ├── logger.py      # Logging configuration
│   ├── prompts.py     # OpenAI system prompts
│   └── utils.py       # Utility functions
├── logs/              # Application logs
├── main.py           # FastAPI application
├── Dockerfile        # Container definition
└── docker-compose.yml # Container orchestration
```

## Architecture

### System Architecture
```mermaid
graph TB
    Client[Client] --> API[FastAPI Application]
    API --> Redis[(Redis Queue)]
    API --> Logger[Logger System]
    
    subgraph Worker Processing
        Redis --> Worker[Background Worker]
        Worker --> PDFProcessor[PDF Processor]
        PDFProcessor --> OpenAI[OpenAI GPT-4V API]
        PDFProcessor --> Storage[File Storage]
    end
    
    Logger --> FileSystem[File System Logs]
    Logger --> Console[Console Output]
    
    Worker --> Callback[Callback URL]
    Worker --> Results[(Results Storage)]
```

### Workflow Diagram
```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI
    participant R as Redis
    participant W as Worker
    participant P as PDF Processor
    participant O as OpenAI API
    participant CB as Callback URL

    C->>A: POST /submit-job/ (PDF files)
    A->>A: Generate job_id
    A->>R: Store initial job status
    A->>C: Return job_id
    
    activate W
    W->>R: Poll for new jobs
    R-->>W: Job details
    W->>P: Process PDF
    
    loop Each Page
        P->>O: Send image for analysis
        O-->>P: Return structured data
        P->>P: Merge results
    end
    
    W->>R: Update job status
    
    opt If callback_url provided
        W->>CB: Send results
    end
    deactivate W
    
    C->>A: GET /job/{job_id}
    A->>R: Get job status
    R-->>A: Return results
    A->>C: Return job status/results
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- OpenAI for GPT-4 Vision API
- FastAPI for the web framework
- PyMuPDF for PDF processing
