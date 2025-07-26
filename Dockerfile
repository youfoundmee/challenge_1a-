# Stage 1: Build Environment
# Use a slim Python image and specify the platform
FROM --platform=linux/amd64 python:3.10-slim-bullseye AS builder

# Create a virtual environment to keep dependencies isolated
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final Production Image
# Use the same base image for a smaller final size
FROM --platform=linux/amd64 python:3.10-slim-bullseye

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Set the working directory in the container
WORKDIR /app

# Copy your Python script into the container
COPY process_pdfs.py .

# Make the Python script executable from the command line
ENV PATH="/opt/venv/bin:$PATH"

# Set the default command to run when the container starts
CMD ["python", "process_pdfs.py"]