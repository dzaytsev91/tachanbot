FROM dzaytsev/python-3.8-slim-git-ffmpeg:latest
COPY . /app
WORKDIR app
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT python main.py
