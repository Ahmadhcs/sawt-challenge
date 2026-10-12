# Arabic Open-Source Model Evaluation

I did not run these models. Hardware and latency figures are from model cards and papers, or estimated from model size. 


## 1. Speech-to-text: Qwen3-ASR-1.7B
- Model: Qwen/Qwen3-ASR-1.7B
- License: Apache 2.0, commercial use allowed

### Why it fits
It is a dedicated speech recognition model that lists arabic among its supported languages, and it supports both streaming and offline transcription in one model. On the only public multi dialect arabic asr benchmark I found it has the lowest cer on Saudi speech of all 33 open models, and the lowest average cer across all six test sets. I believe character accuracy matters here because menu search already tolerates small spelling differences. 

### Evidence
Open universal arabic ASR leaderboard, benchmark of 33 open source models on 6 multi dialect Arabic test sets, all scored zero shot with the same Arabic text normalization. SADA is saudi tv speech, a 10.7 hour test set covering 10 dialects, mostly saudi which fits the use case here. 

The table below shows the relevant models: 

| Model | Size | SADA WER | SADA CER | Average WER | Average CER |
|---|---|---|---|---|---|
| Qwen3-ASR-1.7B | 1.7B | 45.53 | 19.90 | 33.36 | 12.33 |
| Gemma 4 E4B | 4.5B effective | 43.40 | 20.96 | 32.98 | 13.71 |
| omniASR LLM 7B (#1 by average WER) | 7B | 41.61 | 24.95 | 28.32 | 12.52 |
| NVIDIA Conformer-CTC large Arabic + LM | ~120M | 44.52 | 23.76 | 32.91 | 13.84 |
| Whisper large-v3 | 1.55B | 55.96 | 34.62 | 36.86 | 17.21 |

How I read these numbers:
- Dialect is the problem not arabic in general: The leaderboard paper breaks SADA down by dialect: Whisper large-v3 scores 28% WER on modern standard arabic but 49% on najdi and 60% on khaleeji. A model's overall arabic score says little about saudi callers, so I rank by the SADA columns.
- WER and CER disagree, and for this agent CER matters more: omniASR llm 7B gets the most whole words right on Saudi speech, but qwen3-asr gets the most letters right, at a quarter of the size. My menu search already tolerates small spelling differences, so a transcript that's close at the letter level is usable.
- Whisper large-v3, the common default is clearly worse on Saudi speech.
- The tiny NVIDIA Conformer with around 120M parameters is surprisingly competitive and very fast, which makes it worth a latency comparison if running oru own tests. 
- 45% WER sounds bad, but sada is long, spontaneous TV speech with overlapping speakers. Short restaurant orders over a known vocabulary should do much better. Not a claim by me, but a hypothesis to run. 
- These numbers are zero shot. NVIDIA reported that fine tuning an open model on SADA cut saudi dialect WER from 55% to 30%, so fine tuning is the obvious next step if the base model misses the bar.

### Hardware and latency
- Size: 1.7B parameters. In 16 bit that is roughly 4–5 GB of GPU memory, so it fits on a single mid level GPU.
- Speed: the Open asr leaderboard lists an inverse real time factor of about 148, so a 5 second utterance takes roughly 35ms of compute in batch mode, the figure is from english benchmarks.
- Streaming: supported through vLLM. The report gives a time to first token of 92ms for the smaller 0.6B model, it gives no number for 1.7B, so I'd measure it.
- Numbers I care about: WER and CER on saudi speech, accuracy on dish names, quantities and sizes, code switched words, and latency from end of speech to final transcript.

### How I would test it
- Data: the SADA test set , plus about 200 recorded restaurant orders from at least 10 saudi dialect speakers, some wiht background noises. 
- Metrics: WER and CER after the same Arabic normalization the agent uses, entity accuracy on dish names, quantities, sizes and neighborhood names, scored separately because those are what break orders, and latency, measured the way the leaderboard paper does it. 
- Edge cases: one-word answers, corrections, arabic and western digits, English words, and noise. 
- Pass criteria: entity accuracy greater or equals to 95% and WER less than 15% on the restaurant set, no worse than the leaderboard numbers on SADA, final transcript less than 500ms after the caller stops (p95) on one GPU.

### Alternative: Gemma 4 E4B
Apache 2.0, 4.5B effective parameters.

Has a slightly better saudi word accuracy, SADA WER 43.4. I chose Qwen3-ASR because it is a dedicated, smaller ASR model with documented streaming support, and has better character accuracy. Gemma 4 e4b is a general model that also accepts audio, so it is heavier per utterance and its streaming behavior is not documented. If the restaurant test set showed Gemma clearly ahead on entity accuracy, I'd switch.



## 2. LLM: Qwen3-30B-A3B-Instruct-2507
- Model: Qwen/Qwen3-30B-A3B-Instruct-2507 
- License:  Apache 2.0 commercial use allowed


### Why it fits
This agent needs three things from the LLM: understanding Saudi Arabic, reliable tool calling, and speed. This model is a mixture of experts model: 30.5B parameters in total, but only 3.3B are used for each token. It has the knowledge of a large model at close to the speed of a small one, which is the right shape for a live call. It supports native tool calling and a 262K context window, far more than the  around 4K tokens this agent needs per turn. Thinking models reason before answering, which helps accuracy but adds latency to every reply, which is why I went for a non thinking model. 

### Evidence
| Source | Benchmark | Result | What it tells me |
|---|---|---|---|
| HELM Arabic (Stanford CRFM) | 7 Arabic benchmarks | Qwen3 235B is the best open-weights model (mean 0.786); Arabic-specific open models scored below multilingual ones | The Qwen3 family is strong in Arabic. The bigger sibling is measured here; 30B-A3B is not. |
| Arabic Prompts with English Tools (2026) | Berkeley Function Calling, translated to Arabic | Tested qwen3-30b among 5 open models tool calling accuracy drops 5–10% when the user speaks Arabic | Arabic tool calling is measurably harder, so validation must live in code. Keep tool descriptions in English. |
| Qwen model card | BFCL-v3 (tool use) | 65.1 | English tool calling a baseline only |

The evidence gap: no public benchmark measures tool calling in saudi dialect from what I could find. 

### Hardware and latency
- Memory: About 61 GB for weights in 16 bit, about 31 GB in FP8 , or about 17 GB with 4 bit quantization, plus memory for the KV cache.Estimated from 30.5B parameters.
- Speed: With only 3.3B active parameters, generation speed should be close to a small dense model. For a ~3K-token prompt and a short reply on one H100 with vLLM, I'd expect a few hundred ms to first token (estimate).
- Context: 262K tokens natively
- Numbers I care about: task success per conversation, tool selection and argument accuracy, invalid output rate, time to first token (p50 and p95), tokens per second.

### How I would test it
- Data: this repo's scenario conversations, extended to about 100 saudi dialect conversations.
- Metrics: task success in this case the final order state is correct, tool selection accuracy, argument accuracy, invalid tool calls per conversation, prices in the reply that did not come from a tool, and latency 
- Edge cases: caller gives everything in one sentence, changes an earlier answer, ambiguous dishes, unavailable items after a branch change, complaints mid order.
- Pass criteria: task success is greater than 95% across all runs, tool selection is greater than 98%, prices are not hallucinated. 

### Alternative: ALLaM-7B-Instruct-preview
Built by HUMAIN trained on 5.2T tokens including 1.2T mixed Arabic and English, and scores 67.78 on Arabic MMLU. On ArabFuncBench it picks the correct tool 92.3% of the time. I did not choose it for two reasons, its context window is only 4,096 tokens, which is tight once you add the tool schemas, order state and history, and its model card doesn't document tool calling. Had the saudi cultural fleuncy mattered more than tool fluency in our use case it would've been picked. 


## 3. Text-to-speech: NAMAA-Saudi-TTS

- Model: NAMAA-Space/NAMAA-Saudi-TTS
- License: MIT, commercial use allowed with attribution

### Why it fits
A restaurant phone line is a commercial product, so the license comes first. This is the only open model I found that is both tuned for Saudi Arabic and licensed for commercial use. It is built on Chatterbox Multilingual, an MIT-licensed 0.5B-parameter model that supports 23 languages including arabic and can clone a voice from a short reference clip, so the restaurant can pick one consistent Saudi voice. The model with the strongest Saudi evidence, Habibi-TTS, is licensed non commercial. I use its published results as the quality bar this model has to meet.

### Evidence
To be fair, this is the weakest layer of evidence: 

| Source | What it shows | Caveat |
|---|---|---|
| NAMAA model card | Saudi-dialect fine-tune; voice cloning optional | No published evaluation numbers. The card lists missing diacritics and number handling as known weaknesses. |
| Chatterbox model card | Arabic is one of 23 supported languages; preferred over ElevenLabs in side-by-side evaluations | The preference claim is the vendor's own, and not Arabic-specific. |
| Habibi paper (the alternative) | An open model can match commercial TTS on Saudi speech: WER 16.89 vs ElevenLabs v3's 18.94 on the Saudi test set | Shows what's achievable, not how NAMAA performs. |

### Hardware and latency
- Size: about 0.5B parameters, roughly 1–2 GB of GPU memory in 16 bit, so it fits on any modern GPU.
- Speed: no published latency for the open model. Chatterbox's "sub-200ms" figure refers to Resemble's paid hosted service, not the open weights. It's an autoregressive model on a Llama backbone, so it can produce audio in chunks rather than waiting for the whole sentence, but time to first audio has to be measured.
- Numbers I care about: Native speaker ratings for naturalness and dialect, time to first audio, real time factor, and accuracy on dish names, digits and English words.

### How I would test it
- Data: 100 real agent replies from the scenario tests, containing dish names, prices, quantities, neighborhood names, 6-digit order IDs, and English menu words.
- Metrics: back transcription, a targeted check that every number, dish name and order ID is pronounced correctly, and ratings from at least 10 saudi listeners for naturalness and "sounds Saudi" on a scale from 1-5, blind against Habibi-TTS SAU and the current ElevenLabs voice.
- Edge cases: English words inside Arabic sentences, long dish names, and questions vs statements.
- Pass criteria: 100% correct numbers and order IDs, back transcription CER less than 10%, listener ratings goe 3.5 for naturalness and dialect, time to first audio loe 300ms per sentence on one GPU. 

### Alternative: Habibi-TTS 
From what I could fine, the strongest published Saudi evidence of any open TTS model.



## Limitations
- I did not run any of these models, all latency and memory figures are from model cards or estimated from model size.
- STT: the Saudi numbers come from one independent leaderboard, Qwen's own report gives no arabic specific results.
- LLM: Arabic evidence is for the Qwen3 family or for Modern Standard Arabic, no benchmark covers saudi dialect tool calling.
- TTS: my recommended model has no published evaluation numbers, the only saudi TTS evidence is from the Habibi authors' own paper, and that model has a non commercial license. The listener test would be the real decision point.


## Sources
 
**Speech-to-text**
- [Qwen3-ASR-1.7B model card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
- [Qwen3-ASR Technical Report](https://arxiv.org/abs/2601.21337)
- [Open Universal Arabic ASR Leaderboard](https://huggingface.co/spaces/elmresearchcenter/open_universal_arabic_asr_leaderboard)
- [Open Universal Arabic ASR Leaderboard paper](https://arxiv.org/abs/2412.13788)
- [SADA dataset](https://ieee-dataport.org/node/14747)
- [NVIDIA fine-tune on SADA](https://www.middleeastainews.com/p/nvidia-halves-saudi-dialect-errors)
- [Gemma 4 release under Apache 2.0](https://rits.shanghai.nyu.edu/ai/google-releases-gemma-4-frontier-open-models-under-apache-2-0/)
**LLM**
- [Qwen3-30B-A3B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507)
- [HELM Arabic, Stanford CRFM](https://crfm.stanford.edu/2025/12/18/helm-arabic.html)
- [Arabic Prompts with English Tools: A Benchmark](https://arxiv.org/abs/2601.05101)
- [ALLaM-7B-Instruct-preview model card](https://huggingface.co/humain-ai/ALLaM-7B-Instruct-preview)
- [ArabFuncBench](https://huggingface.co/datasets/lsadouk1111/ArabFuncBench)
**Text-to-speech**
- [NAMAA-Saudi-TTS model card](https://huggingface.co/NAMAA-Space/NAMAA-Saudi-TTS)
- [Chatterbox model card, Resemble AI](https://huggingface.co/ResembleAI/chatterbox)
- [Habibi: Unified-Dialectal Arabic Speech Synthesis](https://arxiv.org/abs/2601.13802)
- [Habibi-TTS repository](https://github.com/SWivid/Habibi-TTS)
- [NAMAA-Saudi-TTS-V2 model card](https://huggingface.co/NAMAA-Space/NAMAA-Saudi-TTS-V2)
- [F5-TTS paper](https://arxiv.org/abs/2410.06885)
