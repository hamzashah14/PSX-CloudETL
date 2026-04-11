FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Create and switch to a non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:8004", "app:app"]