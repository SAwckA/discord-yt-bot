FROM python:3.11.8-bookworm

WORKDIR /app

COPY download_ffmpeg.sh /app/
RUN ./download_ffmpeg.sh

COPY poetry.lock pyproject.toml /app/
RUN pip install poetry
RUN python -m poetry config virtualenvs.create false
RUN python -m poetry install --no-interaction --no-ansi
RUN apt update && apt install libopus-dev -y &&  apt-get install libopus0 -y

COPY main.py ydl.py /app/

CMD ["python", "main.py"]

