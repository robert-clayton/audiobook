import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set
from .logger import get_logger

logger = get_logger(__name__)


class ProcessingCache:
    """Cache system for tracking processed files and enabling resume capability."""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "processing_cache.json"
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save cache: {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """Generate hash for file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Could not hash file {file_path}: {e}")
            return ""
    
    def is_processed(self, file_path: str, series_name: str) -> bool:
        """Check if a file has been processed."""
        file_hash = self._get_file_hash(file_path)
        if not file_hash:
            return False
        
        cache_key = f"{series_name}:{file_path}"
        cached_hash = self.cache.get(cache_key)
        
        return cached_hash == file_hash
    
    def mark_processed(self, file_path: str, series_name: str):
        """Mark a file as processed."""
        file_hash = self._get_file_hash(file_path)
        if file_hash:
            cache_key = f"{series_name}:{file_path}"
            self.cache[cache_key] = file_hash
            self._save_cache()
    
    def get_pending_files(self, input_dir: str, series_name: str) -> List[str]:
        """Get list of files that need processing."""
        pending = []
        input_path = Path(input_dir)
        
        if not input_path.exists():
            return pending
        
        for file_path in input_path.rglob("*.txt"):
            if not self.is_processed(str(file_path), series_name):
                pending.append(str(file_path))
        
        return sorted(pending)
    
    def clear_series_cache(self, series_name: str):
        """Clear cache for a specific series."""
        keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{series_name}:")]
        for key in keys_to_remove:
            del self.cache[key]
        self._save_cache()
        logger.info(f"Cleared cache for series: {series_name}")
    
    def clear_all_cache(self):
        """Clear all cache."""
        self.cache = {}
        self._save_cache()
        logger.info("Cleared all processing cache")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        series_counts = {}
        for key in self.cache.keys():
            series_name = key.split(":", 1)[0]
            series_counts[series_name] = series_counts.get(series_name, 0) + 1
        
        return {
            "total_cached_files": len(self.cache),
            "series_count": len(series_counts),
            "files_per_series": series_counts
        }


class TTSModelCache:
    """Cache for TTS model instances to avoid reloading."""
    
    _instance = None
    _models = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_model(self, model_name: str):
        """Get or create TTS model instance."""
        if model_name not in self._models:
            logger.info(f"Loading TTS model: {model_name}")
            # This would be implemented in tts_instance.py
            from ..processors.tts_instance import TTSInstance
            self._models[model_name] = TTSInstance(model_name)
        
        return self._models[model_name]
    
    def clear_cache(self):
        """Clear all cached models."""
        self._models.clear()
        logger.info("Cleared TTS model cache")


class AudioCache:
    """Cache for processed audio files."""
    
    def __init__(self, cache_dir: str = ".audio_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def get_cached_audio(self, text_hash: str, narrator: str) -> Optional[str]:
        """Get cached audio file path if it exists."""
        cache_file = self.cache_dir / f"{text_hash}_{narrator}.wav"
        return str(cache_file) if cache_file.exists() else None
    
    def cache_audio(self, text_hash: str, narrator: str, audio_path: str):
        """Cache an audio file."""
        cache_file = self.cache_dir / f"{text_hash}_{narrator}.wav"
        try:
            import shutil
            shutil.copy2(audio_path, cache_file)
            logger.debug(f"Cached audio: {cache_file}")
        except Exception as e:
            logger.warning(f"Could not cache audio: {e}")
    
    def clear_cache(self):
        """Clear all cached audio files."""
        try:
            import shutil
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(exist_ok=True)
            logger.info("Cleared audio cache")
        except Exception as e:
            logger.error(f"Could not clear audio cache: {e}")


# Global cache instances
processing_cache = ProcessingCache()
tts_cache = TTSModelCache()
audio_cache = AudioCache()

