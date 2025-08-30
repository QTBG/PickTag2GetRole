#!/bin/bash
# Script to initialize the data directory for first-time setup

# Create data directory if it doesn't exist
if [ ! -d "data" ]; then
    echo "Creating data directory..."
    mkdir -p data
    echo "Data directory created successfully."
else
    echo "Data directory already exists."
fi

# Set proper permissions
chmod 755 data

echo "Data directory initialization complete."