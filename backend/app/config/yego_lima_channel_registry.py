"""
LG-2.4 V1 — Lima Growth Channel Registry.

Maps operational channels to DB config names and defines program-to-channel
preference order for capacity allocation.

MANTENIMIENTO:
  - Para cambiar orden de preferencia, modificar PROGRAM_CHANNEL_PREFERENCE.
  - Para agregar canales, agregar entrada en CHANNEL_CODES y CHANNEL_DISPLAY_NAMES.
  - No hardcodear preferencias en otros archivos; importar desde aquí.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

CANONICAL_CHANNEL_CODES = ("CALL_CENTER", "SAC", "BOT")

CHANNEL_DISPLAY_NAMES: Dict[str, str] = {
    "CALL_CENTER": "Call Center",
    "SAC": "SAC",
    "BOT": "Bot / WhatsApp",
}

CHANNEL_DB_TO_CODE: Dict[str, str] = {
    "Call Center": "CALL_CENTER",
    "SAC": "SAC",
    "Bot / WhatsApp": "BOT",
}

CHANNEL_CODE_TO_DB: Dict[str, str] = {
    "CALL_CENTER": "Call Center",
    "SAC": "SAC",
    "BOT": "Bot / WhatsApp",
}

PROGRAM_CHANNEL_PREFERENCE: Dict[str, List[str]] = {
    "PROGRAM_HIGH_VALUE_RECOVERY": ["CALL_CENTER", "SAC", "BOT"],
    "PROGRAM_CHURN_PREVENTION": ["CALL_CENTER", "SAC", "BOT"],
    "PROGRAM_14_90": ["BOT", "CALL_CENTER", "SAC"],
    "PROGRAM_ACTIVE_GROWTH": ["BOT", "CALL_CENTER", "SAC"],
}


def get_channel_preference(program_code: str) -> List[str]:
    return PROGRAM_CHANNEL_PREFERENCE.get(program_code, list(CANONICAL_CHANNEL_CODES))


def get_channel_display_name(channel_code: str) -> str:
    return CHANNEL_DISPLAY_NAMES.get(channel_code, channel_code)


def resolve_db_channel_to_code(db_channel: str) -> str:
    return CHANNEL_DB_TO_CODE.get(db_channel, db_channel.upper().replace(" ", "_").replace("/", "_"))


def list_channel_registry_for_audit() -> List[Dict[str, object]]:
    return [
        {
            "code": code,
            "display_name": get_channel_display_name(code),
            "db_name": CHANNEL_CODE_TO_DB.get(code),
        }
        for code in CANONICAL_CHANNEL_CODES
    ]
