import re
import os
import traceback
from tqdm import tqdm
import nltk
from nltk.tokenize import sent_tokenize
from ..validators.validate_file import validate
from ..utils.audio import change_playback_speed, merge_audio, modulate_audio
from ..utils.colors import RED, GREEN, RESET

class TTSProcessor:
    DEFAULT_NARRATOR = 'onyx'

    CHUNK_SIZE_COQUI = 250
    CHUNK_SIZE_QWEN = 750

    def __init__(self, file_name, config, output_dir, tmp_dir, max_chunk_size=None):
        self._ensure_nltk_data()
        self.file_name = file_name
        self.narrator = config.get('narrator', TTSProcessor.DEFAULT_NARRATOR)
        self.cleaned_file_name = None
        if config.get('tts_engine') == 'qwen':
            from .tts_qwen import QwenTTSInstance
            self.tts = QwenTTSInstance()
            default_chunk_size = TTSProcessor.CHUNK_SIZE_QWEN
        else:
            from .tts_instance import TTSInstance
            self.tts = TTSInstance()
            default_chunk_size = TTSProcessor.CHUNK_SIZE_COQUI
        self.output_dir = output_dir
        self.tmp_dir = tmp_dir
        self.max_chunk_size = max_chunk_size or default_chunk_size
        self.speakers = self._load_speakers()
        self.character_speaker_mappings = config.get('mappings', {})
        self.pause_config = config.get('pause', {})
        self.system = config.get('system', {})
        self.will_modulate_system = self.system.get('modulate', True)

        self.base_output_file = os.path.splitext(os.path.basename(self.file_name))[0]
        self.output_path = os.path.join(self.output_dir, f"{self.base_output_file}.wav")
        self.output_path_mp3 = os.path.join(self.output_dir, f"{self.base_output_file}.mp3")

    def _ensure_nltk_data(self):
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            nltk.download('punkt_tab')

    def _load_speakers(self):
        if not os.path.isdir('speakers'):
            raise FileNotFoundError("speakers directory not found.")
        return [os.path.splitext(f)[0] for f in os.listdir('speakers') if f.endswith('.wav')]

    def validate_file(self, replacements):
        if not os.path.isfile(self.file_name):
            print(f"{RED}File '{self.file_name}' not found.{RESET}")
            raise FileNotFoundError(self.file_name)
        self.cleaned_file_name = validate(self.file_name, replacements)

    def check_already_exists(self):
        return os.path.exists(self.output_path) or os.path.exists(self.output_path_mp3)

    def convert_text_to_speech(self):
        temp_files = []
        if self.check_already_exists():
            return

        with open(self.cleaned_file_name, 'r', encoding='utf-8') as f:
            text = f.read()

        parts = re.split(r'(<<SPEAKER=[^>]+>>.*?<</SPEAKER>>)', text, flags=re.DOTALL)
        parts = [p for p in parts if p.strip()]

        progress = tqdm(total=len(text), desc=f"{GREEN}Progress{RESET}", unit="char")
        for idx, part in enumerate(parts):
            match = re.search(r'<<SPEAKER=([^>]+)>>(.+?)<</SPEAKER>>', part, flags=re.DOTALL)
            if match:
                name = self.narrator if match.group(1)=='default' else match.group(1).lower()
                content = match.group(2)
            else:
                name, content = self.narrator, part

            is_system = (name == 'system')
            if is_system:
                name = self.system.get('voice', TTSProcessor.DEFAULT_NARRATOR)

            if name not in self.speakers and name in self.character_speaker_mappings:
                name = self.character_speaker_mappings[name]

            speaker_file = os.path.join('speakers', f"{name}.wav")
            chunks = self._split_text(content)

            # Collect chunks that need generation
            pending_texts = []
            pending_paths = []
            pending_indices = []  # (cidx, is_system) for post-processing
            pending_char_counts = []

            for cidx, chunk in enumerate(chunks):
                if not chunk.strip():
                    progress.update(len(chunk))
                    continue

                out_wave_name = f'{self.base_output_file}_part{idx}_{name}_{cidx}.wav'
                out_wav_path = os.path.join(self.tmp_dir, out_wave_name)
                if not os.path.exists(out_wav_path):
                    text_chunk = chunk.strip('<>').strip()
                    pending_texts.append(text_chunk)
                    pending_paths.append(out_wav_path)
                    pending_indices.append((cidx, is_system))
                    pending_char_counts.append(len(chunk))
                else:
                    progress.update(len(chunk))
                temp_files.append(out_wav_path)

            if not pending_texts:
                continue

            pause = self.pause_config.get(name)

            # Generate TTS in batches with progress updates after each batch
            try:
                batch_size = 5
                if hasattr(self.tts, 'tts_batch_to_files'):
                    for i in range(0, len(pending_texts), batch_size):
                        batch_texts = pending_texts[i:i + batch_size]
                        batch_paths = pending_paths[i:i + batch_size]
                        batch_chars = pending_char_counts[i:i + batch_size]
                        self.tts.tts_batch_to_files(
                            texts=batch_texts, speaker_wav=speaker_file,
                            file_paths=batch_paths, language="en", pause=pause)
                        progress.update(sum(batch_chars))
                else:
                    for text_chunk, out_wav_path, char_count in zip(
                            pending_texts, pending_paths, pending_char_counts):
                        self.tts.tts_to_file(text=text_chunk, speaker_wav=speaker_file,
                                             file_path=out_wav_path, language="en", pause=pause)
                        progress.update(char_count)
            except Exception as e:
                print(f"\t{RED}Error on TTS: {e}{RESET}")
                traceback.print_exc()
                # Remove paths for chunks that failed
                for p in pending_paths:
                    if not os.path.exists(p):
                        temp_files = [f for f in temp_files if f != p]
                continue

            # Post-process system voice chunks
            for (cidx, was_system), out_wav_path in zip(pending_indices, pending_paths):
                if was_system and os.path.exists(out_wav_path):
                    if self.will_modulate_system:
                        modulate_audio(out_wav_path, self.tmp_dir)
                    if self.system.get('speed', 1.0) != 1.0:
                        change_playback_speed(out_wav_path, self.system['speed'])
        progress.close()

        if len(temp_files) > 1 and merge_audio(temp_files, self.output_path):
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        else:
            os.rename(temp_files[0], self.output_path)
        print(f"\t{GREEN}Saved!{RESET}")

    def _split_text(self, text):
      sentences = sent_tokenize(text)
      chunks = []

      for sentence in sentences:
          sentence = sentence.strip()
          if not sentence:
              continue

          # If the sentence itself is longer than max_chunk_size, hard-split it
          if len(sentence) > self.max_chunk_size:
              words = sentence.split()
              buffer = ""
              for word in words:
                  if len(buffer) + len(word) + 1 > self.max_chunk_size:
                      chunks.append(buffer.strip())
                      buffer = ""
                  buffer += word + " "
              if buffer:
                  chunks.append(buffer.strip())
          else:
              chunks.append(sentence)

      return chunks


    def clean_up(self):
        if self.cleaned_file_name and os.path.exists(self.cleaned_file_name):
            os.remove(self.cleaned_file_name)