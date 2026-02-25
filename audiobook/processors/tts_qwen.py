import os
import numpy as np
import torch
import soundfile as sf
from ..utils.colors import YELLOW, RESET

PAUSE_SECONDS = None

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
        import contextlib, io, os as _os
        # Suppress noisy import/load warnings (flash-attn, SoX not found, etc.)
        # Redirect fd-level stderr to suppress subprocess "not recognized" messages
        _old_stderr_fd = _os.dup(2)
        _devnull_fd = _os.open(_os.devnull, _os.O_WRONLY)
        _os.dup2(_devnull_fd, 2)
        _os.close(_devnull_fd)
        try:
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                from qwen_tts import Qwen3TTSModel
                self.model = Qwen3TTSModel.from_pretrained(
                    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                    device_map="cuda:0",
                    dtype=torch.bfloat16,
                )
        finally:
            _os.dup2(_old_stderr_fd, 2)
            _os.close(_old_stderr_fd)
        # Suppress "Setting pad_token_id to eos_token_id" warning
        gen_cfg = self.model.model.generation_config
        if gen_cfg.pad_token_id is None and gen_cfg.eos_token_id is not None:
            gen_cfg.pad_token_id = gen_cfg.eos_token_id
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
        wav = wavs[0]
        if PAUSE_SECONDS:
            wav = np.concatenate([wav, np.zeros(int(sr * PAUSE_SECONDS), dtype=wav.dtype)])
        sf.write(file_path, wav, sr)

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
                if PAUSE_SECONDS:
                    wav = np.concatenate([wav, np.zeros(int(sr * PAUSE_SECONDS), dtype=wav.dtype)])
                sf.write(path, wav, sr)
