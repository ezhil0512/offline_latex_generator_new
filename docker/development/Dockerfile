# Dockerfile.dev - Development Environment Skeleton
FROM python:3.10-slim

# Install system dependencies including Poppler and pdflatex
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications
COPY requirements.txt pyproject.toml ./

# Install packages in editable mode
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e .

# Expose Flask default port and debug port
EXPOSE 5000
EXPOSE 5678

ENV OLG_ENV=development
ENV FLASK_APP=src/offline_latex_generator/main.py
ENV FLASK_DEBUG=1

# Command to run development server
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
