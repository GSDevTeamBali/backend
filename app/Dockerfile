FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN useradd --create-home appuser
USER appuser

EXPOSE 3033

# FastAPI is a framework, not a server. Uvicorn is the ASGI server that runs it:
#   main:app  -> the `app` object from the file main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3033"]