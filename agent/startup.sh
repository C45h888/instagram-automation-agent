#!/bin/bash
# Pull Llama 3.1 8B Instruct model into Ollama with retry on failure
# This script runs inside the ollama container or as an init step

# Ollama registry model — Llama 3.1 has official tool-calling support
MODEL="llama3.1:8b"

# Skip pull if model is already present (avoids unnecessary network check on restarts)
if ollama list 2>/dev/null | grep -q "$MODEL"; then
    echo "$MODEL already present, skipping pull."
else
    echo "Pulling $MODEL from Ollama registry..."
    if ollama pull "$MODEL"; then
        echo "Model pulled successfully."
    else
        echo "Pull failed, retrying in 10 seconds..."
        sleep 10
        if ollama pull "$MODEL"; then
            echo "Model pulled successfully on retry."
        else
            echo "ERROR: Model pull failed after 2 attempts. Pull manually with:"
            echo "  docker exec -it ollama ollama pull $MODEL"
        fi
    fi
fi
