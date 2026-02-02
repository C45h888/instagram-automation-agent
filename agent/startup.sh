#!/bin/bash
# Pull Nemotron 4 8B model into Ollama with retry on failure
# This script runs inside the ollama container or as an init step

echo "Pulling NVIDIA Nemotron 4 8B Q5_K_M model..."

ollama pull nemotron:8b-q5_K_M && echo "Model pulled successfully" || {
    echo "First attempt failed, retrying in 10 seconds..."
    sleep 10
    ollama pull nemotron:8b-q5_K_M && echo "Model pulled on retry" || {
        echo "WARN: Model pull failed after 2 attempts. Pull manually with:"
        echo "  docker exec -it ollama ollama pull nemotron:8b-q5_K_M"
    }
}
