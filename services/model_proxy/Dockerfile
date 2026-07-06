FROM python:3.11-slim
WORKDIR /app
COPY shared/ shared/
COPY services/model_proxy/ services/model_proxy/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8004
CMD ["uvicorn", "services.model_proxy.app:app", "--host", "0.0.0.0", "--port", "8004"]
