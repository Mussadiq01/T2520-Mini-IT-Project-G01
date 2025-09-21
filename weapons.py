from dataclasses import dataclass
from typing import Optional, List

@dataclass
class Weapon:
    name: str
    damage: int
    swing_ms: int
    cooldown_ms: int
    arc_deg: int
    sprite_name: str
    # optional combat effects
    stun_ms: int = 0
    bleed_duration_ms: int = 0
    bleed_interval_ms: int = 0
    # optional projectile
    projectile_damage: int = 0
    projectile_sprite: Optional[str] = None
    projectile_speed: float = 0.0          # pixels per second
    projectile_life_ms: int = 0

# Balanced defaults; sprites fall back if missing on disk.
WEAPON_LIST: List[Weapon] = [
    Weapon(
        name="Sword",
        damage=5,
        swing_ms=220,
        cooldown_ms=280,
        arc_deg=120,
        sprite_name="sword.png"
    ),
    Weapon(
        name="Mallet",
        damage=10,
        swing_ms=280,
        cooldown_ms=600,
        arc_deg=100,
        sprite_name="mallet.png",
        stun_ms=600
    ),
    Weapon(
        name="Dagger",
        damage=3,
        swing_ms=150,
        cooldown_ms=50,
        arc_deg=0,  # thrust in main.py
        sprite_name="dagger.png"
    ),
    Weapon(
        name="Katana",
        damage=8,
        swing_ms=300,
        cooldown_ms=220,
        arc_deg=360,
        sprite_name="katana.png",
        bleed_duration_ms=2500,
        bleed_interval_ms=500
    ),
    Weapon(
        name="The Descender",
        damage=15,
        swing_ms=240,
        cooldown_ms=200,
        arc_deg=130,
        sprite_name="the_descender.png",
        projectile_damage=5,
        projectile_sprite="sunball.png",
        projectile_speed=500.0,
        projectile_life_ms=1500
    ),
]

__all__ = ["Weapon", "WEAPON_LIST"]
