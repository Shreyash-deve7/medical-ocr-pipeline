FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install bitsandbytes for Qwen-VL 4-bit quantization support
RUN pip install --no-cache-dir "bitsandbytes>=0.46.1"

COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist ./static

RUN mkdir -p uploads

ENV MEDVAULT_STATIC_DIR=/app/static
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
