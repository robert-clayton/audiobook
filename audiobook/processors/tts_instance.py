"""Singleton wrapper around the Coqui TTS (XTTS v2) model for GPU-accelerated speech synthesis."""

from TTS.api import TTS


class TTSInstance:
    """Singleton Coqui TTS model loaded once on GPU and shared across all processing."""

    _inst = None

    def __new__(cls, model="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True):
        if not cls._inst:
            cls._inst = super().__new__(cls)
            cls._inst._init(model, progress_bar)
        return cls._inst

    def _init(self, model_name, progress_bar):
        """Load the Coqui TTS model onto CUDA."""
        self.model = TTS(model_name=model_name, progress_bar=progress_bar).to("cuda")

    @classmethod
    def unload(cls):
        """Free the model and release GPU memory."""
        if cls._inst:
            del cls._inst.model
            cls._inst = None

    def tts_to_file(self, **kwargs):
        """Synthesize speech and write it to a WAV file. Delegates to Coqui TTS."""
        return self.model.tts_to_file(**kwargs)
