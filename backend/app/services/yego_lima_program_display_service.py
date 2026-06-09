"""
YEGO Lima Growth — Program Display Names (LG-UX-R2.8)
Single source of truth for human-readable program names.
"""
PROGRAM_DISPLAY_NAMES = {
    "PROGRAM_CHURN_PREVENTION": "Churn Prevention",
    "PROGRAM_ACTIVE_GROWTH": "Active Growth",
    "PROGRAM_14_90": "Programa 14/90",
    "PROGRAM_HIGH_VALUE_RECOVERY": "High Value Recovery",
}

def get_display_name(program_code: str) -> str:
    return PROGRAM_DISPLAY_NAMES.get(program_code, program_code)

def get_all_programs():
    return [{"code": k, "name": v} for k, v in PROGRAM_DISPLAY_NAMES.items()]
