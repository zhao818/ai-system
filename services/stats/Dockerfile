FROM python:3.11-slim
WORKDIR /app
COPY shared/ shared/
COPY services/stats/ services/stats/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8005
CMD ["uvicorn", "services.stats.app:app", "--host", "0.0.0.0", "--port", "8005"]
