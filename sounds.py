import pygame
from pathlib import Path
from typing import Dict, Optional

# Simple sound / music manager for the project.
# Usage:
#   import sounds
#   sounds.play_music('menu_theme.ogg')
#   sounds.play_sfx('swing.wav')
#   sounds.set_master_volume(0.5)
#   sounds.stop_music()
#
# Put your audio files in a folder named 'sounds' or 'audio' at project root.
# Supported extensions for SFX: .wav .ogg .mp3
# For music you pass the exact filename (looked up in the same folders).

BASE_DIR = Path(__file__).parent
SOUND_DIRS = [BASE_DIR / 'sounds', BASE_DIR / 'audio']
SUPPORTED_SFX_EXT = ('.wav', '.ogg', '.mp3')

class SoundManager:
    def __init__(self):
        self._mixer_ready = False
        self._ensure_mixer()
        self.sfx_cache: Dict[str, pygame.mixer.Sound] = {}
        self.music_volume = 1.0
        self.sfx_volume = 1.0
        self.master_volume = 1.0

    def _ensure_mixer(self):
        if self._mixer_ready:
            return
        try:
            if not pygame.get_init():
                pygame.init()
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._mixer_ready = True
        except Exception:
            self._mixer_ready = False

    # ---------- File Lookup Helpers ----------
    def _find_file(self, name: str) -> Optional[Path]:
        p = Path(name)
        if p.is_file():
            return p
        # try each sound directory; for SFX allow extension guessing
        for d in SOUND_DIRS:
            if not d.exists():
                continue
            # exact name first
            exact = d / name
            if exact.exists():
                return exact
            # guess extensions for sfx names without extension
            if not p.suffix:
                for ext in SUPPORTED_SFX_EXT:
                    cand = d / f"{name}{ext}"
                    if cand.exists():
                        return cand
        return None

    # ---------- Music ----------
    def play_music(self, filename: str, volume: float = 1.0, loops: int = -1, fade_ms: int = 600):
        self._ensure_mixer()
        if not self._mixer_ready:
            return
        path = self._find_file(filename)
        if not path:
            return
        try:
            pygame.mixer.music.load(str(path))
            self.music_volume = max(0.0, min(1.0, volume))
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
            pygame.mixer.music.play(loops=loops, fade_ms=fade_ms)
        except Exception:
            pass

    def stop_music(self, fade_ms: int = 600):
        try:
            pygame.mixer.music.fadeout(fade_ms)
        except Exception:
            pass

    def set_music_volume(self, v: float):
        self.music_volume = max(0.0, min(1.0, v))
        try:
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
        except Exception:
            pass

    # ---------- SFX ----------
    def load_sfx(self, name: str) -> Optional[pygame.mixer.Sound]:
        self._ensure_mixer()
        if not self._mixer_ready:
            return None
        key = name.lower()
        if key in self.sfx_cache:
            return self.sfx_cache[key]
        path = self._find_file(name)
        if not path:
            return None
        try:
            snd = pygame.mixer.Sound(str(path))
            self.sfx_cache[key] = snd
            return snd
        except Exception:
            return None

    def play_sfx(self, name: str, volume: float = 1.0):
        snd = self.load_sfx(name)
        if not snd:
            return
        vol = max(0.0, min(1.0, volume)) * self.sfx_volume * self.master_volume
        try:
            snd.set_volume(vol)
            snd.play()
        except Exception:
            pass

    def set_sfx_volume(self, v: float):
        self.sfx_volume = max(0.0, min(1.0, v))

    def set_master_volume(self, v: float):
        self.master_volume = max(0.0, min(1.0, v))
        # refresh music volume immediately
        try:
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
        except Exception:
            pass

    # ---------- Utilities ----------
    def preload(self, *names: str):
        for n in names:
            self.load_sfx(n)

    def pause_all(self):
        try:
            pygame.mixer.pause()
        except Exception:
            pass

    def resume_all(self):
        try:
            pygame.mixer.unpause()
        except Exception:
            pass

    def stop_all_sfx(self):
        try:
            pygame.mixer.stop()
        except Exception:
            pass

# Global singleton
manager = SoundManager()

# Convenience module-level functions
play_music = manager.play_music
stop_music = manager.stop_music
play_sfx = manager.play_sfx
set_music_volume = manager.set_music_volume
set_sfx_volume = manager.set_sfx_volume
set_master_volume = manager.set_master_volume
pause_all = manager.pause_all
resume_all = manager.resume_all
stop_all_sfx = manager.stop_all_sfx
preload = manager.preload

__all__ = [
    'play_music','stop_music','play_sfx','set_music_volume','set_sfx_volume',
    'set_master_volume','pause_all','resume_all','stop_all_sfx','preload','manager'
]
