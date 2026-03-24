#!/bin/bash
# Pull Qwen2.5-7B Instruct GGUF model into Ollama with retry on failure
# This script runs inside the ollama container or as an init step

# Primary: HuggingFace GGUF path (most up-to-date)
MODEL_HF="hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q4_k_m"
# Fallback: Ollama registry name (more reliable but may be slightly older quantization)
MODEL_REGISTRY="qwen2.5:7b"
# Short name — how Ollama stores and lists the model locally
MODEL_SHORT="qwen2.5-7b-instruct-q4_k_m"

# Skip pull if model is already present (avoids unnecessary network check on restarts)
if ollama list 2>/dev/null | grep -q "$MODEL_SHORT"; then
    echo "$MODEL_SHORT already present, skipping pull."
else
    echo "Pulling $MODEL_HF from HuggingFace..."
    if ollama pull "$MODEL_HF"; then
        echo "Model pulled successfully from HuggingFace."
    else
        echo "HuggingFace pull failed, retrying in 10 seconds..."
        sleep 10
        if ollama pull "$MODEL_HF"; then
            echo "Model pulled successfully on retry from HuggingFace."
        else
            echo "HuggingFace pull failed after 2 attempts, trying Ollama registry..."
            if ollama pull "$MODEL_REGISTRY"; then
                echo "Model pulled successfully from Ollama registry."
            else
                echo "First registry attempt failed, retrying in 10 seconds..."
                sleep 10
                if ollama pull "$MODEL_REGISTRY"; then
                    echo "Model pulled successfully on retry from Ollama registry."
                else
                    echo "ERROR: Model pull failed after all attempts. Pull manually with:"
                    echo "  docker exec -it ollama ollama pull $MODEL_HF"
                    echo "  or: docker exec -it ollama ollama pull $MODEL_REGISTRY"
                fi
            fi
        fi
    fi
fi
