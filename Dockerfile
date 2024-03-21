FROM python:3.11.8-bookworm

WORKDIR /app

RUN apt update && apt install -y --no-install-recommends ffmpeg

RUN pip install poetry

COPY poetry.lock pyproject.toml /app/
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

COPY main.py ydl.py /app/

CMD ["python", "main.py"]
