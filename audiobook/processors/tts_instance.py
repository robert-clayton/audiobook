from TTS.api import TTS


class TTSInstance:
    _inst = None
    _initialized = False

    def __new__(
        cls, model="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True
    ):
        if not cls._inst:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __init__(self, model="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True):
        if not self._initialized:
            self._init(model, progress_bar)
            self._initialized = True

    def _init(self, model_name, progress_bar):
        try:
            self.model = TTS(model_name=model_name, progress_bar=progress_bar).to("cuda")
        except Exception as e:
            # Fallback to CPU if CUDA is not available
            print(f"CUDA not available, falling back to CPU: {e}")
            self.model = TTS(model_name=model_name, progress_bar=progress_bar)

    def tts_to_file(self, **kwargs):
        if not hasattr(self, 'model') or self.model is None:
            raise AttributeError("TTS model not properly initialized")
        return self.model.tts_to_file(**kwargs)
