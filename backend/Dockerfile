FROM python:3.11-slim

WORKDIR /app

# Copy the emd source package
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install emd + its dependencies
RUN pip install --no-cache-dir -e .

# Install backend-specific deps
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
