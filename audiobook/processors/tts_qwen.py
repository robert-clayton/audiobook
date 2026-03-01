"""Singleton wrapper around the Qwen3 TTS Base model for GPU-accelerated voice-cloned speech synthesis."""

import os
import numpy as np
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
    """Singleton Qwen3 TTS model loaded once on GPU and shared across all processing."""

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

    @classmethod
    def unload(cls):
        """Free the model and release GPU memory."""
        if cls._inst:
            del cls._inst.model
            cls._inst._prompt_cache.clear()
            cls._inst = None
            torch.cuda.empty_cache()

    def _get_voice_clone_prompt(self, speaker_wav):
        """Build or retrieve a cached voice clone prompt for the given speaker WAV.

        Uses reference text transcript if available, otherwise falls back to
        x-vector-only mode (lower quality).
        """
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

    def _pad_silence(self, wav, sr, pause):
        """Append silence of `pause` seconds to the waveform, if specified."""
        if pause:
            return np.concatenate([wav, np.zeros(int(sr * pause), dtype=wav.dtype)])
        return wav

    def tts_to_file(self, text, speaker_wav, file_path, language="en", pause=None, **kwargs):
        """Synthesize a single text string and write the result to a WAV file."""
        lang = LANGUAGE_MAP.get(language, language)
        prompt = self._get_voice_clone_prompt(speaker_wav)

        wavs, sr = self.model.generate_voice_clone(
            text=text,
            language=lang,
            voice_clone_prompt=prompt,
        )
        sf.write(file_path, self._pad_silence(wavs[0], sr, pause), sr)

    def tts_batch_to_files(self, texts, speaker_wav, file_paths, language="en", pause=None, batch_size=5):
        """Synthesize multiple texts in batches and write each result to its corresponding WAV file."""
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
                sf.write(path, self._pad_silence(wav, sr, pause), sr)
