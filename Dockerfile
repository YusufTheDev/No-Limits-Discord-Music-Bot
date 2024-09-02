# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Make sure the dotenv file is present
COPY .env .env

# Expose the port your bot will be running on (optional, if you plan to monitor it externally)
EXPOSE 5000

# Run the bot
CMD ["python", "main.py"]