# Use an official Python runtime as a base image
FROM python:3.12-slim

# Install curl and necessary packages, including libgit2-dev for pygit2
RUN apt-get update && \
    apt-get install -y curl build-essential libpq-dev libgit2-dev

## install minio client (mc)
RUN curl https://dl.min.io/client/mc/release/linux-amd64/mc \
    --create-dirs \
    -o /usr/local/bin/mc && \
    chmod +x /usr/local/bin/mc

# Install Poetry using the official installer and add it to PATH
RUN curl -sSL https://install.python-poetry.org | python3 -
    ENV PATH="/root/.local/bin:${PATH}"

## Create and set the working directory
WORKDIR /app

# Copy Poetry configuration files first to leverage Docker cache
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root

# Copy the rest of the application code
COPY . .


# Set env variables (optional, if needed)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1


# Expose the necessary port(s)
EXPOSE 8000

# Start the application with Uvicorn when the container is run
# CMD ["./dev_start.sh"]
