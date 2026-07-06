FROM python:3.11-slim
RUN pip install opencode-ai
WORKDIR /app
COPY shared/ shared/
COPY services/executor/ services/executor/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8002
CMD ["uvicorn", "services.executor.app:app", "--host", "0.0.0.0", "--port", "8002"]
