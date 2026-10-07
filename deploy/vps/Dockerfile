FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=2
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py engine.py ./
COPY static ./static
RUN groupadd --gid 10001 cemitx && useradd --uid 10001 --gid 10001 --no-create-home cemitx
USER 10001:10001
EXPOSE 8080
CMD ["waitress-serve", "--listen=0.0.0.0:8080", "--threads=4", "--call", "app:create_app"]
