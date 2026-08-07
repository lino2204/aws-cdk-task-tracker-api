# Dev environment for aws-cdk-task-tracker-api
# Provides a reproducible toolchain: Node.js (for CDK CLI) + Python + CDK + project deps.
# This image is for LOCAL DEVELOPMENT only (running cdk synth/deploy, pytest, flake8) —
# it is not what gets deployed to AWS; Lambda code is packaged separately by CDK itself.

FROM node:22-slim

# --- System deps: Python + build tools ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    git \
    && rm -rf /var/lib/apt/lists/*

# --- AWS CDK CLI (global npm install) ---
RUN npm install -g aws-cdk@2.150.0

WORKDIR /app

# --- Python virtual environment ---
ENV VIRTUAL_ENV=/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# --- Install Python deps first (better layer caching) ---
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-dev.txt

# --- Copy the rest of the project ---
COPY . .

# Default: drop into a shell. Run cdk synth / pytest / flake8 manually,
# or override this command, e.g.: docker run ... task-api-dev cdk synth
CMD ["bash"]
