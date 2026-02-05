#!/bin/bash
# Pull NVIDIA Nemotron-Orchestrator-8B model into Ollama with retry on failure
# This script runs inside the ollama container or as an init step

echo "Pulling NVIDIA Nemotron-Orchestrator-8B Q5_K_M from HuggingFace..."

ollama pull hf.co/MaziyarPanahi/Nemotron-Orchestrator-8B-GGUF:Q5_K_M && echo "Model pulled successfully" || {
    echo "First attempt failed, retrying in 10 seconds..."
    sleep 10
    ollama pull hf.co/MaziyarPanahi/Nemotron-Orchestrator-8B-GGUF:Q5_K_M && echo "Model pulled on retry" || {
        echo "WARN: Model pull failed after 2 attempts. Pull manually with:"
        echo "  docker exec -it ollama ollama pull hf.co/MaziyarPanahi/Nemotron-Orchestrator-8B-GGUF:Q5_K_M"
    }
}
