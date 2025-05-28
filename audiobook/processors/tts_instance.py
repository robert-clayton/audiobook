from TTS.api import TTS

class TTSInstance:
    _inst = None

    def __new__(cls, model="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True):
        if not cls._inst:
            cls._inst = super().__new__(cls)
            cls._inst._init(model, progress_bar)
        return cls._inst

    def _init(self, model_name, progress_bar):
        self.model = TTS(model_name=model_name, progress_bar=progress_bar).to("cuda")

    def tts_to_file(self, **kwargs):
        return self.model.tts_to_file(**kwargs)
