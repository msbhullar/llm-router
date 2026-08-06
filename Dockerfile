FROM python:3.13-slim

WORKDIR /app

COPY requirements-router.txt .
RUN pip install --no-cache-dir -r requirements-router.txt
RUN python -m spacy download en_core_web_sm

COPY router_service/ router_service/
COPY classifier/ classifier/

EXPOSE 8000

CMD ["uvicorn", "router_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
