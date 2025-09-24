import pygame
from pathlib import Path
from typing import Optional, Dict

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

        # Try to load persisted master volume from save.py (non-fatal)
        try:
            # local import to avoid coupling at module import time elsewhere
            import save
            data = save.load_player_data() or {}
            mv = data.get("master_volume")
            if mv is not None:
                try:
                    mvf = float(mv)
                    self.master_volume = max(0.0, min(1.0, mvf))
                except Exception:
                    pass
        except Exception:
            pass

        # Apply loaded master volume to mixer if available
        try:
            if self._mixer_ready:
                try:
                    pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
                except Exception:
                    pass
                try:
                    chs = pygame.mixer.get_num_channels()
                    for i in range(chs):
                        try:
                            # multiply channel by sfx_volume as channels represent sfx outputs
                            pygame.mixer.Channel(i).set_volume(self.sfx_volume * self.master_volume)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    def _ensure_mixer(self):
        if self._mixer_ready:
            return
        try:
            pygame.init()
            pygame.mixer.init()
            self._mixer_ready = True
        except Exception:
            self._mixer_ready = False

    def _find_file(self, name: str) -> Optional[Path]:
        p = Path(name)
        if p.is_file():
            return p
        for d in SOUND_DIRS:
            if not d.exists():
                continue
            exact = d / name
            if exact.exists():
                return exact
            if not p.suffix:
                for ext in SUPPORTED_SFX_EXT:
                    candidate = d / f"{name}{ext}"
                    if candidate.exists():
                        return candidate
        return None

    # ---------- Music ----------
    def play_music(self, filename: str, volume: float = 1.0, loops: int = -1, fade_ms: int = 600):
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

    def set_music_volume(self, volume: float):
        self.music_volume = max(0.0, min(1.0, volume))
        try:
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
        except Exception:
            pass

    # ---------- SFX ----------
    def load_sfx(self, name: str) -> Optional[pygame.mixer.Sound]:
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

    def set_sfx_volume(self, volume: float):
        self.sfx_volume = max(0.0, min(1.0, volume))

    def set_master_volume(self, volume: float):
        self.master_volume = max(0.0, min(1.0, volume))
        try:
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
        except Exception:
            pass

    # ---------- Utilities ----------
    def preload(self, *names: str):
        for name in names:
            self.load_sfx(name)

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

# Module-level MASTER_VOLUME kept in sync for existing code that inspects sounds.MASTER_VOLUME
MASTER_VOLUME = manager.master_volume

# Convenience functions
play_music = manager.play_music
stop_music = manager.stop_music
play_sfx = manager.play_sfx
set_music_volume = manager.set_music_volume
set_sfx_volume = manager.set_sfx_volume
# keep original alias for master volume setter
set_master_volume = manager.set_master_volume
# wrapper so module-level MASTER_VOLUME stays in sync
def _set_master_volume_wrapper(volume: float):
    try:
        manager.set_master_volume(volume)
    except Exception:
        pass
    global MASTER_VOLUME
    try:
        MASTER_VOLUME = manager.master_volume
    except Exception:
        MASTER_VOLUME = float(getattr(manager, 'master_volume', 1.0))
set_master_volume = _set_master_volume_wrapper
pause_all = manager.pause_all
resume_all = manager.resume_all
stop_all_sfx = manager.stop_all_sfx
preload = manager.preload

__all__ = [
    'play_music', 'stop_music', 'play_sfx', 'set_music_volume', 'set_sfx_volume',
    'set_master_volume', 'pause_all', 'resume_all', 'stop_all_sfx', 'preload', 'manager', 'MASTER_VOLUME'
]
