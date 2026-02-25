import os
import torch
import soundfile as sf
from ..utils.colors import YELLOW, RESET

LANGUAGE_MAP = {
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "pt": "Portuguese",
    "ar": "Arabic",
    "ru": "Russian",
}


class QwenTTSInstance:
    _inst = None

    def __new__(cls):
        if not cls._inst:
            cls._inst = super().__new__(cls)
            cls._inst._init()
        return cls._inst

    def _init(self):
        from qwen_tts import Qwen3TTSModel

        self.model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device_map="cuda:0",
            dtype=torch.bfloat16,
        )
        self._prompt_cache = {}

    def _get_voice_clone_prompt(self, speaker_wav):
        if speaker_wav in self._prompt_cache:
            return self._prompt_cache[speaker_wav]

        ref_text_path = os.path.splitext(speaker_wav)[0] + ".txt"
        if os.path.isfile(ref_text_path):
            with open(ref_text_path, "r", encoding="utf-8") as f:
                ref_text = f.read().strip()
            prompt = self.model.create_voice_clone_prompt(
                ref_audio=speaker_wav,
                ref_text=ref_text,
                x_vector_only_mode=False,
            )
        else:
            print(
                f"\t{YELLOW}Warning: No transcript found at {ref_text_path}, "
                f"using x_vector_only_mode (lower quality){RESET}"
            )
            prompt = self.model.create_voice_clone_prompt(
                ref_audio=speaker_wav,
                x_vector_only_mode=True,
            )

        self._prompt_cache[speaker_wav] = prompt
        return prompt

    def tts_to_file(self, text, speaker_wav, file_path, language="en", **kwargs):
        lang = LANGUAGE_MAP.get(language, language)
        prompt = self._get_voice_clone_prompt(speaker_wav)

        wavs, sr = self.model.generate_voice_clone(
            text=text,
            language=lang,
            voice_clone_prompt=prompt,
        )
        sf.write(file_path, wavs[0], sr)

    def tts_batch_to_files(self, texts, speaker_wav, file_paths, language="en", batch_size=5):
        lang = LANGUAGE_MAP.get(language, language)
        prompt = self._get_voice_clone_prompt(speaker_wav)

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_paths = file_paths[i:i + batch_size]
            langs = [lang] * len(batch_texts)

            wavs, sr = self.model.generate_voice_clone(
                text=batch_texts,
                language=langs,
                voice_clone_prompt=prompt,
            )
            for wav, path in zip(wavs, batch_paths):
                sf.write(path, wav, sr)
