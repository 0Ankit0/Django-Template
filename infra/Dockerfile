FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install project dependencies
RUN uv sync --frozen --no-dev

# Copy project
COPY . .

# Create non-root user
RUN groupadd --system django && \
    useradd --system --create-home --gid django django && \
    chown -R django:django /app

USER django

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000

COPY infra/entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]