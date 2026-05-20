# Open Medical LLMs for Text-Only Clinical Reasoning

Ниже приведён уточнённый список открытых медицинских LLM, которые подходят для **text-only** задач в медицине, включая **clinical reasoning**, **medical QA**, **clinical summarization** и **biomedical reasoning**.

> Важно: список **не включает image-модели** и **не включает multimodal/VLM**.  
> Фокус только на **текстовых open models**, доступных через Hugging Face или репозитории, которые можно использовать для локального запуска и API-тестирования.

---

## 1) Meditron-7B

**Описание:**  
Одна из самых известных открытых медицинских LLM, адаптированная под медицинский домен. Подходит для medical QA, clinical prompts и текстового reasoning.

**Hugging Face:**  
https://huggingface.co/epfl-llm/meditron-7b

**Организация:**  
https://huggingface.co/epfl-llm

**Тип:**  
- text-only  
- medical / clinical language model  

**Плюсы:**  
- известная open medical LLM  
- специализирована на медицинском домене  
- удобна для локального тестирования  

**Минусы:**  
- русский язык не является сильной стороной  
- на сложных clinical кейсах на русском качество может снижаться  

**Поддержка русского языка:**  
Ограниченная. Лучше тестировать и на русском, и на английском переводе того же запроса.

**Пример локального запуска через vLLM:**  
```bash
python -m vllm.entrypoints.openai.api_server \
  --model epfl-llm/meditron-7b \
  --port 8001
```

---

## 2) Meditron-70B

**Описание:**  
Более крупная версия Meditron, ориентированная на более сильное medical reasoning и более высокое качество ответов по сравнению с 7B.

**Hugging Face:**  
https://huggingface.co/epfl-llm/meditron-70b

**Тип:**  
- text-only  
- medical reasoning / instruction-following  

**Плюсы:**  
- сильнее подходит для сложного reasoning  
- одна из самых интересных open medical моделей высокого класса  

**Минусы:**  
- требует значительно больше вычислительных ресурсов  
- локальный запуск сложнее  
- русский язык поддерживается ограниченно  

**Поддержка русского языка:**  
Ограниченная. Лучше использовать A/B-тест: русский prompt и английский перевод.

**Пример запуска через vLLM:**  
```bash
python -m vllm.entrypoints.openai.api_server \
  --model epfl-llm/meditron-70b \
  --tensor-parallel-size 4 \
  --port 8002
```

---

## 3) BioMistral-7B

**Описание:**  
Открытая biomedical language model на базе Mistral. Хороший компромисс между размером модели, качеством и удобством локального запуска.

**Hugging Face:**  
https://huggingface.co/BioMistral/BioMistral-7B

**Организация:**  
https://huggingface.co/BioMistral

**Тип:**  
- text-only  
- biomedical / medical text model  

**Плюсы:**  
- удобна для MVP и локального тестирования  
- легче запускать, чем 70B модели  
- хороша для biomedical QA и текстовых medical tasks  

**Минусы:**  
- на сложных clinical reasoning задачах может уступать более крупным моделям  
- русский язык не является приоритетным языком  

**Поддержка русского языка:**  
Слабая или умеренная. Общий русский может пониматься, но клиническая точность на русском может снижаться.

**Пример локального запуска через vLLM:**  
```bash
python -m vllm.entrypoints.openai.api_server \
  --model BioMistral/BioMistral-7B \
  --port 8003
```

---

## 4) OpenBioLLM-Llama3-70B

**Описание:**  
Крупная открытая biomedical LLM, ориентированная на биомедицинские тексты, biomedical QA и reasoning в научно-медицинском домене.

**Hugging Face:**  
https://huggingface.co/aaditya/OpenBioLLM-Llama3-70B

**Профиль автора/организации:**  
https://huggingface.co/aaditya

**Тип:**  
- text-only  
- biomedical reasoning / QA / domain-adapted LLM  

**Плюсы:**  
- сильный biomedical vocabulary и knowledge coverage  
- полезна для сравнения с clinical-oriented моделями  
- крупный современный open checkpoint  

**Минусы:**  
- тяжёлая для локального запуска  
- может быть сильнее в biomedical knowledge, чем в практическом clinical style reasoning  
- русский язык поддерживается ограниченно  

**Поддержка русского языка:**  
Ограниченная. Лучше тестировать через английский перевод, если нужен более стабильный результат.

**Пример локального запуска через vLLM:**  
```bash
python -m vllm.entrypoints.openai.api_server \
  --model aaditya/OpenBioLLM-Llama3-70B \
  --tensor-parallel-size 4 \
  --port 8004
```

---

## 5) PMC_LLaMA_13B

**Описание:**  
Известная open biomedical/medical language model, обученная на корпусах из медицинской и биомедицинской литературы. Полезна как baseline в сравнении с более новыми моделями.

**Hugging Face:**  
https://huggingface.co/axiong/PMC_LLaMA_13B

**Тип:**  
- text-only  
- biomedical / medical text model  

**Плюсы:**  
- исторически важная open biomedical model  
- полезна как baseline  
- подходит для biomedical text tasks  

**Минусы:**  
- модель уже не самая современная  
- может уступать более новым instruction-tuned medical моделям  
- русский язык поддерживается слабо  

**Поддержка русского языка:**  
Слабая. Для русскоязычного clinical reasoning вряд ли будет оптимальным вариантом.

**Пример локального запуска через vLLM:**  
```bash
python -m vllm.entrypoints.openai.api_server \
  --model axiong/PMC_LLaMA_13B \
  --port 8005
```

---

# Итоговый список

| Модель | Ссылка |
|---|---|
| Meditron-7B | https://huggingface.co/epfl-llm/meditron-7b |
| Meditron-70B | https://huggingface.co/epfl-llm/meditron-70b |
| BioMistral-7B | https://huggingface.co/BioMistral/BioMistral-7B |
| OpenBioLLM-Llama3-70B | https://huggingface.co/aaditya/OpenBioLLM-Llama3-70B |
| PMC_LLaMA_13B | https://huggingface.co/axiong/PMC_LLaMA_13B |

---

# Практические рекомендации

## Для локального MVP
Наиболее удобные кандидаты:
- Meditron-7B  
- BioMistral-7B  
- PMC_LLaMA_13B  

## Для максимального качества среди open models
Наиболее интересные кандидаты:
- Meditron-70B  
- OpenBioLLM-Llama3-70B  

## Для тестов на русском языке
У всех моделей поддержка русского языка ограниченная.  
Рекомендуется сравнивать три режима:
1. исходный запрос на русском  
2. перевод запроса на английский  
3. русский запрос с англоязычной медицинской терминологией  

---

# Важное замечание

У большинства open medical моделей **нет стабильного официального бесплатного managed API**.  
На практике “free use” обычно означает:
- запуск локально на своём сервере  
- self-hosted inference через vLLM/TGI  
- либо использование community endpoints, если они доступны  

Поэтому для тестового веб-приложения лучше всего строить архитектуру через **self-hosted OpenAI-compatible endpoints**.
