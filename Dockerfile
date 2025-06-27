# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for Nmap and network operations
RUN apt-get update && apt-get install -y nmap procps && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable to ensure python prints things without buffering
ENV PYTHONUNBUFFERED 1

# Run the application
# We will run the main.py which will contain the main loop for scanning
# and also start the uvicorn server in a separate thread.
# For now, we just define the command. The actual implementation will be in main.py
CMD ["python", "pingpoint/main.py"]
