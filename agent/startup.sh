#!/bin/bash
# Pull NVIDIA Nemotron-Orchestrator-8B model into Ollama with retry on failure
# This script runs inside the ollama container or as an init step

MODEL="hf.co/MaziyarPanahi/Nemotron-Orchestrator-8B-GGUF:Q4_K_M"

# Skip pull if model is already present (avoids unnecessary network check on restarts)
if ollama list 2>/dev/null | grep -q "Q4_K_M"; then
    echo "Model already present, skipping pull."
else
    echo "Pulling NVIDIA Nemotron-Orchestrator-8B Q4_K_M from HuggingFace..."
    ollama pull "$MODEL" && echo "Model pulled successfully" || {
        echo "First attempt failed, retrying in 10 seconds..."
        sleep 10
        ollama pull "$MODEL" && echo "Model pulled on retry" || {
            echo "WARN: Model pull failed after 2 attempts. Pull manually with:"
            echo "  docker exec -it ollama ollama pull $MODEL"
        }
    }
fi
