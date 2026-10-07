FROM python:3.11-slim
WORKDIR /app
RUN pip install torch --no-cache-dir --index-url  https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir laya[serve]==0.3.28
ENV LAYA_MODELS=english
CMD ["laya-serve"]