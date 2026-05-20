# healthcare LLM models

For most healthcare developers in 2025-2026, MedGemma 27B offers the best balance of performance, efficiency, and openness for text-based medical reasoning, while GLM-4.5V or MedGemma 4B Multimodal are strong choices for medical imaging applications.

Here are the top 5 open LLM models available for free use that are trained and specialized in medicine:

## 1. MedGemma (Google)
Variants: 4B Multimodal, 27B Text, 27B Multimodal
Performance: 87.7% on MedQA (USMLE-style questions)
Strengths: Medical imaging (chest X-rays), clinical reasoning, electronic health record interpretation
Efficiency: 4B variant runs on mobile hardware; 27B runs on a single GPU
License: Open weights via Google’s Health AI Developer Foundations

Strengths: Purpose-built for healthcare; 87.7% on MedQA (27B); chest X-ray report generation; EHR interpretation
Note: Can run on a single GPU; 4B variant suitable for mobile hardware

google/medgemma-27b-text-it

## 2. GLM-4.5V (Zhipu AI)
Parameters: 106B total, 12B active (Mixture-of-Experts)
Strengths: Excels at medical imaging analysis (radiology, pathology), processes medical videos and long clinical documents
Notable: State-of-the-art among open-source models on 41 multimodal benchmarks
License: Open source

Context window: 65.5K tokens
Strengths: Vision-language multimodal (images, video, documents), 3D-RoPE, “Thinking Mode,” supports Chinese and English

## 3. OpenAI GPT-OSS-120B
Parameters: ~117B (5.1B active, MoE architecture)
Strengths: Strong performance on health/medical benchmarks, chain-of-thought reasoning for clinical diagnostics
License: Apache 2.0 (commercial use permitted)

Context window: 128K tokens
Strengths: Strong reasoning, health benchmarks, agentic capabilities (function calling, code execution)


## 4. MedSigLIP (Google)
Type: Lightweight image and text encoder
Strengths: Medical classification, search, and retrieval tasks; runs on mobile hardware
Best for: Structured output tasks like image classification and medical image retrieval
License: Open weights via Google HAI-DEF

## 5. BioMistral / Med-PaLM Open Alternatives (e.g., Meditron)
Meditron (EPFL): 7B and 70B parameter models fine-tuned on medical literature (PubMed, clinical guidelines)
BioMistral: Mistral-based model fine-tuned on PubMed Central
Strengths: Strong on PubMedQA and MedMCQA benchmarks, lightweight enough for on-premises deployment
License: Open source (Apache 2.0 / Llama license depending on variant)

## Meditron-70B (finetuned) 

outperforms Llama-2-70B, GPT-3.5, and Flan-PaLM on multiple medical reasoning tasks

Multilingual evaluation: The authors automatically translated their benchmark into 7 languages to assess multilingual generalization, marking the first large-scale multilingual evaluation of medical LLMs. However, the model itself was not explicitly trained on multilingual medical data
Performance: Superior to existing open-source medical models and competitive with proprietary counterparts on English medical QA benchmarks

## Multilingual Medical LLM (MMed-Llama 3)


 Лучший выбор для русского языка: MMed-Llama 3
Обучена на 25.5 млрд токенов медицинского корпуса на 6 языках, включая русский
8B параметров, конкурирует с GPT-4 на мультиязычных медицинских бенчмарках
Открытая модель