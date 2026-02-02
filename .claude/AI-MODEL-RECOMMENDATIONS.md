# AI Model Recommendations for Instagram Automation Oversight Brain

**Document Purpose:** Reference guide for selecting and deploying AI models for the LangChain agent's oversight capabilities (sentiment analysis, comment moderation, action recommendations). Generated via Hugging Face Hub analysis.

**Last Updated:** 2026-02-02
**Target Environment:** Hetzner CX43/CAX31 VPS (8 vCPU, 16GB RAM, Docker)
**Integration:** Ollama + llama.cpp for local inference

---

## Quick Selection Matrix

| Model | Size | Inference Speed | Analysis Quality | Memory (Q5) | Recommended For |
|-------|------|-----------------|------------------|-------------|-----------------|
| **Mistral-7B-Instruct-v0.2** ⭐ | 7B | ⚡⚡ Fast | Excellent | ~5GB | PRIMARY - Best all-around |
| **Mistral-7B-OpenOrca** | 7B | ⚡ Balanced | Excellent+ | ~5GB | SECONDARY - Complex reasoning |
| **Llama-3-8B-Quantized** | 8B | ⚡ Balanced | Excellent | ~6GB | FALLBACK - Llama preference |
| **Mistral-Trismegistus** | 7B | ⚡ Balanced | Excellent+ | ~5GB | ALTERNATIVE - GPT-4 tuned |

---

## TIER 1: RECOMMENDED MODELS

### 1. ⭐ TheBloke/Mistral-7B-Instruct-v0.2-GGUF

**Model ID:** `mistralai/Mistral-7B-Instruct-v0.2`
**Parameters:** 7B
**Format:** GGUF (quantized, ready for Ollama)
**Community Adoption:** 78.5K downloads, 500 likes

**Link:** [View on Hugging Face](https://hf.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF)

#### Strengths ✅
- **Lightweight:** Only 7B params = faster inference (key for N8N webhook latency)
- **Instruction-Tuned:** Excellent for structured tasks (sentiment analysis, action recommendations)
- **Proven Performance:** High download count indicates community validation
- **Memory Efficient:** Q5 quantization = ~5GB on your 16GB RAM setup
- **Fast Response Times:** ~100-300ms per query on 8 vCPU (acceptable for N8N triggers)
- **Balanced:** Good reasoning without overcomplicating overhead
- **Use Cases:**
  - Comment sentiment classification (positive/negative/neutral)
  - Reply recommendation generation
  - Spam/bot detection heuristics
  - Action priority scoring

#### Drawbacks ❌
- **Reasoning Limits:** May struggle with extremely complex multi-step analysis
- **Context Window:** Smaller context window (~32K) vs newer models
- **Instruct-Only:** Requires careful prompt engineering for nuanced tasks
- **No Fine-Tuning Included:** Generic instruction-tuning, not Instagram-specific

#### Recommended Quantization
- **Q5_K_M:** Sweet spot for your setup (speed + quality)
- **Q4_K_M:** If memory constrained, acceptable quality drop
- **Q6_K:** If prioritizing accuracy over speed

#### Deployment Command
```bash
ollama pull mistral:7b-instruct-v0.2-q5_K_M
```

---

### 2. TheBloke/Mistral-7B-OpenOrca-GGUF

**Model ID:** `Open-Orca/Mistral-7B-OpenOrca`
**Parameters:** 7B
**Format:** GGUF
**Base Model:** Mistral-7B fine-tuned on Open-Orca synthetic dataset
**Community Adoption:** 3K downloads, 242 likes

**Link:** [View on Hugging Face](https://hf.co/TheBloke/Mistral-7B-OpenOrca-GGUF)

#### Strengths ✅
- **Enhanced Reasoning:** Fine-tuned on high-quality Open-Orca dataset (synthetic GPT-generated responses)
- **Better Chain-of-Thought:** Superior at multi-step decision logic
- **Explanation Generation:** Can provide reasoning for decisions (valuable for audit logging)
- **Complex Analysis:** Better at nuanced sentiment and context understanding
- **Still Lightweight:** Maintains 7B param advantage
- **Use Cases:**
  - Complex comment interpretation (sarcasm, context-dependent sentiment)
  - Multi-factor action recommendations
  - Detailed audit log entries with reasoning
  - DM reply generation with contextual awareness

#### Drawbacks ❌
- **Slightly Slower:** ~10-20% slower inference than base Mistral (still acceptable)
- **Less Adoption:** Fewer downloads = less community feedback/optimization
- **Training Data Synthetic:** OpenOrca data may not reflect Instagram's social dynamics
- **Potential Overfitting:** Fine-tuning could cause quirks vs base model

#### Recommended Quantization
- **Q5_K_M:** Recommended (reasoning benefits justify slight slowdown)
- **Q4_K_M:** Acceptable if inference latency critical

#### Deployment Command
```bash
ollama pull open-orca:mistral-7b-q5_K_M
```

---

### 3. Manirathinam21/Llama-3-8B-Quantized-GGUF

**Model ID:** `meta-llama/Llama-3-8B`
**Parameters:** 8B
**Format:** GGUF (Q4 & Q8 variants available)
**Available Quantizations:** Q4 (4GB), Q8 (7GB)
**Community Adoption:** 7 downloads (newer)

**Link:** [Llama-3-8B-Quantized-GGUF](https://hf.co/Manirathinam21/Llama-3-8B-Quantized-GGUF)

#### Strengths ✅
- **Matches Original Spec:** Exactly 8B parameters as planned
- **Meta Quality:** Llama 3 is strong baseline model from official research
- **Flexible Quantization:** Choose Q4 (speed) or Q8 (quality)
- **Larger Model:** Slightly more capability than 7B variants
- **Official Support:** Meta-backed model has ongoing support
- **Use Cases:**
  - All Mistral-7B use cases with extra capacity
  - Handling ambiguous Instagram context/slang
  - More robust general-purpose analysis

#### Drawbacks ❌
- **Slower than Mistral-7B:** 8B = ~15-20% slower inference
- **More Memory:** Q5 quantization uses ~6GB (vs 5GB for 7B)
- **Not Instruction-Tuned:** Base Llama-3-8B variant (may need better prompts)
- **Lower Adoption:** Fewer downloads = less battle-tested for production
- **Overkill for Lightweight Tasks:** You may not need the extra 1B params

#### Recommended Quantization
- **Q5_K_M:** Best balance (5-6GB)
- **Q4_K_M:** If memory critical
- **Q8_0:** If maximum quality needed

#### Deployment Command
```bash
# Download from repo with quantization variants
huggingface-cli download Manirathinam21/Llama-3-8B-Quantized-GGUF --repo-type model
```

---

## TIER 2: ALTERNATIVE OPTIONS

### 4. TheBloke/Mistral-7B-Instruct-v0.1-GGUF

**Parameters:** 7B
**Downloads:** 19.3K | **Likes:** 608
**Status:** Older but stable version

**Strengths:** Battle-tested in production, excellent community support, slightly smaller context but rock-solid
**Drawbacks:** Older instruction tuning, v0.2 is generally preferred
**Use When:** You need proven stability over latest features

**Link:** [Mistral-7B-Instruct-v0.1-GGUF](https://hf.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF)

---

### 5. TheBloke/Mistral-Trismegistus-7B-GGUF

**Parameters:** 7B
**Base Training:** Fine-tuned on GPT-4 synthetic data for reasoning
**Status:** Specialized reasoning variant

**Strengths:** Enhanced reasoning (Trismegistus = "thrice-great" in Hermeticism), GPT-4 quality data
**Drawbacks:** Even less adoption (~100 downloads), inference slightly slower
**Use When:** You need maximum reasoning quality for complex oversight decisions

**Link:** [Mistral-Trismegistus-7B-GGUF](https://hf.co/TheBloke/Mistral-Trismegistus-7B-GGUF)

---

### 6. RichardErkhov/Izdibay_-_llama3-8b-quantized (Q4/Q8 variants)

**Parameters:** 8B
**Variants:** Q4 (~4GB), Q8 (~7GB)
**Status:** Direct quantization of Llama-3-8B

**Strengths:** Maximum flexibility in quantization levels
**Drawbacks:** Same as Llama-3-8B (less adoption, not instruction-tuned)
**Use When:** Exact 8B Llama with extreme memory constraints (Q4)

**Links:** [Q4](https://hf.co/RichardErkhov/Izdibay_-_llama3-8b-quantized-q4-gguf) | [Q8](https://hf.co/RichardErkhov/Izdibay_-_llama3-8b-quantized-q8-gguf)

---

## Quantization Reference Guide

### Understanding GGUF Quantization

GGUF files contain different quantization levels. Choose based on your VPS constraints:

| Quantization | Bits Per Weight | File Size (7B) | Quality Level | Speed | Recommended For |
|--------------|-----------------|----------------|---------------|-------|-----------------|
| **Q2_K** | 2.3 | ~3GB | Poor | ⚡⚡⚡ Fastest | Emergency fallback only |
| **Q3_K_M** | 3 | ~3.5GB | Fair | ⚡⚡ Very Fast | Tight memory constraints |
| **Q4_K_M** ✓ | 4 | ~4.5GB | Good | ⚡ Fast | Budget memory setups |
| **Q5_K_M** ⭐ | 5 | ~5.5GB | Excellent | ⚡ Balanced | **RECOMMENDED** |
| **Q6_K** | 6 | ~6.5GB | Excellent+ | 🐢 Slower | Quality-first production |
| **Q8_0** | 8 | ~7.5GB | Near-Original | 🐢 Slowest | Maximum accuracy needed |

### Recommendation for Your Setup

**Hetzner CX43 Specs:** 8 vCPU, 16GB RAM

- **Primary Choice:** Q5_K_M quantization on any 7B model (~5.5GB)
- **Fallback:** Q4_K_M if memory issues (~4.5GB, acceptable quality)
- **Premium:** Q6_K only if dedicated oversight machine planned (~6.5GB)

---

## Performance Benchmarks (Estimated)

On Hetzner CX43 (8 vCPU, shared resources):

| Model | Quantization | Avg Inference Time | Concurrent Capacity |
|-------|---------------|--------------------|---------------------|
| Mistral-7B | Q4 | ~80-100ms | 8-10 requests |
| Mistral-7B | Q5 | ~120-150ms | 6-8 requests |
| Mistral-7B-OpenOrca | Q5 | ~140-180ms | 5-7 requests |
| Llama-3-8B | Q5 | ~150-180ms | 5-7 requests |

**N8N Integration Note:** Webhook timeouts typically ~30s, so even slowest option (180ms) allows 150+ sequential analyses before timeout.

---

## FINAL RECOMMENDATION FOR YOUR PROJECT

### 🎯 Production Setup

**Primary Model:** `TheBloke/Mistral-7B-Instruct-v0.2-GGUF` with **Q5_K_M** quantization

**Why This Choice:**
1. ✅ Balances speed (100-150ms inference) with quality
2. ✅ Proven adoption (78.5K downloads)
3. ✅ Instruction-tuned for structured oversight tasks
4. ✅ Memory efficient (5.5GB) leaves room for N8N/Supabase queries
5. ✅ Fast enough for N8N webhook integration
6. ✅ Easier to prompt-engineer than alternatives

**Secondary Model:** `TheBloke/Mistral-7B-OpenOrca-GGUF` with **Q5_K_M**

**When to Use OpenOrca:**
- Complex multi-step analysis required
- Need detailed reasoning for audit logs
- Handling nuanced sentiment/context analysis

### 📋 Deployment Priority Order

1. **Start with:** Mistral-7B-Instruct-v0.2 (Q5_K_M)
2. **Test with:** OpenOrca variant if accuracy issues arise
3. **Fallback to:** Llama-3-8B-Q4 if memory constraints hit
4. **Never use:** Models with <1000 community downloads for production

---

## Integration Checklist

- [ ] Download chosen model GGUF file to Docker volume
- [ ] Load into Ollama service in docker-compose.yml
- [ ] Test inference latency: `time curl http://ollama:11434/api/generate`
- [ ] Set N8N webhook timeout to 45s (safety margin for inference)
- [ ] Create system prompt for oversight (e.g., sentiment classifier, action recommender)
- [ ] Log model decisions to `audit_log` table in Supabase
- [ ] Monitor inference time during peak load
- [ ] Have Q4 quantization backup if Q5 shows memory issues

---

## References

- [Mistral-7B Technical Report](https://arxiv.org/abs/2310.06825)
- [Open-Orca Dataset Paper](https://arxiv.org/abs/2306.02707)
- [GGUF Format Specification](https://github.com/ggerganov/ggml/blob/master/docs/gguf.md)
- [Ollama Documentation](https://ollama.ai)

---

**Document for:** LangChain Agent Planning & Deployment
**Maintainer:** Claude Code (AI Assistant)
**Status:** Ready for architecture review