# Dockerfile.prod - Production Environment Skeleton
FROM python:3.10-slim

# Install system dependencies including Poppler and pdflatex (minimal installation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications and install them
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src

# Install package
RUN pip install --no-cache-dir .

# Expose server port
EXPOSE 5000

ENV OLG_ENV=production
ENV FLASK_APP=src/offline_latex_generator/main.py

# Command to run production server using gunicorn (added to base requirements/env if needed)
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
