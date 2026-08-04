FROM python:3.12-slim

RUN pip install --no-cache-dir \
      requests==2.34.2 \
      langgraph==1.2.4 \
      mcp==2.0.0 \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5

WORKDIR /app

COPY frozen_apis.py /app/frozen/frozen_apis.py
COPY fixtures /app/frozen/fixtures
