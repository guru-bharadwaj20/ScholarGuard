# ScholarGuard — CPU-only image for the CLI and the API bridge.
#
# The pipeline is CPU-only by design, so this installs the CPU torch wheels
# rather than the ~2.5 GB CUDA build. Training the optional AI classifier is the
# one GPU step in the project and is deliberately NOT part of this image; run
# scripts/train_artifact_classifier.py on a host with a GPU, or the Colab
# notebook, and mount the resulting checkpoint in.
FROM python:3.12-slim

# opencv needs libGL and libglib even in headless use.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so edits to the source do not invalidate the layer. The two
# requirements files share a basename, so they are copied to distinct paths --
# a single COPY of both into one directory would silently keep only the second.
COPY requirements.txt /app/requirements.txt
COPY server/requirements.txt /app/server-requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir -r /app/server-requirements.txt

COPY . .

# Datasets are never baked in: they are large and re-fetchable via scripts/.
# Mount them, e.g. -v $PWD/data:/app/data
VOLUME ["/app/data", "/app/outputs"]

# ANTHROPIC_API_KEY (claim-consistency) and NCBI_CONTACT_EMAIL (data fetching)
# are read from the environment and must never be baked into the image.
ENV PYTHONUNBUFFERED=1

# Default: the API bridge the web UI talks to. For the CLI instead, run
#   docker run --rm -v $PWD/data:/app/data scholarguard \
#       python run_scholarguard.py --pdf data/sample_papers/<paper>.pdf
EXPOSE 8000
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
