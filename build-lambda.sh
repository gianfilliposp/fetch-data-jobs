#!/bin/bash

# Exit on error
set -e

# Base directories
SRC_DIR="lambda"

# Iterate through all directories in src
for dir in "$SRC_DIR"/*; do
    # Get the directory name
    dir_name=$(basename "$dir")
    
    # Skip common_utils directory
    if [ "$dir_name" = "common_utils" ]; then
        echo "Skipping common_utils directory..."
        continue
    fi
    
    echo "Processing $dir..."
    
    echo "Copying common_utils files..."
    cp -r "$SRC_DIR/common_utils"/* "$dir/"
    
    # Check if requirements.txt exists and install dependencies
    if [ -f "$dir/requirements.txt" ]; then
        echo "Installing requirements for $dir_name..."
        pip install -r "$dir/requirements.txt" -t "$build_dir"
    fi
    
    echo "Build completed for $dir_name"
done

echo "All builds completed successfully!"
