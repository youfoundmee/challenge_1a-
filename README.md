# Adobe India Hackathon 2025 - Challenge 1a Solution

This repository contains a high-performance solution for the "Connecting the Dots" PDF processing challenge. The implementation extracts a structured outline (Title, H1, H2, H3) from PDF documents and generates schema-compliant JSON files.

## Approach and Design

The solution is a Python script designed for speed and accuracy, running within a containerized Docker environment.

1.  **Parallel Processing**: It uses Python's `concurrent.futures.ProcessPoolExecutor` to process multiple PDF files in parallel, fully utilizing the 8 CPU cores specified in the challenge environment to minimize total execution time.

2.  **PDF Parsing**: The core parsing logic is handled by the **PyMuPDF** library, which is renowned for its high speed and low memory footprint, making it ideal for the strict performance constraints.

3.  **Structure Extraction**:
    * **Primary Method (ToC)**: The script first attempts to extract the document's embedded Table of Contents (ToC). This is the most reliable source for identifying the intended document structure.
    * **Fallback Method (Heuristic Analysis)**: If a PDF lacks a ToC, the script automatically switches to a heuristic model that analyzes font properties. It identifies the body text's font size and then flags text with significantly larger fonts as potential headings, assigning levels (H1, H2, H3) based on relative font sizes.

## Libraries and Tools

* **Language**: Python 3.10
* **PDF Parsing**: `PyMuPDF` (v1.23.5)
* **Containerization**: Docker

All tools and libraries used are open source and compatible with the `linux/amd64` architecture.

## How to Build and Run

### 1. Build the Docker Image

From the root directory of the project, run the following command:

```sh
docker build --platform linux/amd64 -t pdf-processor .