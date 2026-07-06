FROM python:3.11-slim
WORKDIR /app
COPY shared/ shared/
COPY services/router_service/ services/router_service/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8001
CMD ["uvicorn", "services.router_service.app:app", "--host", "0.0.0.0", "--port", "8001"]
