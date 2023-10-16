FROM python:3.8.0-slim
RUN apt-get update && apt-get install -y git && apt-get install ffmpeg
COPY . /app
WORKDIR app
RUN pip install -r requirements.txt
ENTRYPOINT python main.py
