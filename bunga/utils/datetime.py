# PEP-8
from datetime import timedelta


def get_total_microseconds(td: timedelta) -> int:
    return int(td.total_seconds() * 1_000_000)
