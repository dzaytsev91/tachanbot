FROM python:3.8.0-slim
RUN apt-get update && apt-get install -y git && apt-get -y install ffmpeg && rm -rf /var/lib/apt/lists/
COPY . /app
WORKDIR app
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT python main.py
