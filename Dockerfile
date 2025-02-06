FROM python:3.9-slim

# Add build arguments
ARG OPENAI_API_KEY
ARG REDIS_HOST=redis

# Set environment variables
ENV OPENAI_API_KEY=$OPENAI_API_KEY \
    REDIS_HOST=$REDIS_HOST

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p logs

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
