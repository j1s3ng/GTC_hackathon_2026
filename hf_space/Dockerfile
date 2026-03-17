FROM python:3.11-slim

WORKDIR /app

COPY local_server.py /app/local_server.py
COPY webui /app/webui
COPY data /app/data

ENV RELIEFROUTE_HOST=0.0.0.0
ENV RELIEFROUTE_PORT=7860
ENV HF_MODEL=nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16

EXPOSE 7860

CMD ["python", "local_server.py"]
