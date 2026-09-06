FROM python:3.12-slim AS base

# Create an unprivileged user; the bot never needs root.
RUN useradd --create-home --shell /usr/sbin/nologin botuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY tests ./tests
COPY pytest.ini .

# Secure temp dir for ephemeral session files, owned only by botuser.
RUN mkdir -p /tmp/tgsession_secure && chown -R botuser:botuser /tmp/tgsession_secure /app

USER botuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["python", "-m", "src.main"]
