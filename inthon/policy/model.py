from __future__ import annotations
from enum import Enum, auto

class Capability(Enum):
    NETWORK         = auto()
    FILESYSTEM_READ = auto()
    FILESYSTEM_WRITE= auto()
    SHELL           = auto()
    EMAIL_SEND      = auto()
    CALENDAR_WRITE  = auto()
    PAYMENT_EXECUTE = auto()
    MEMORY_WRITE    = auto()
    DATABASE_WRITE  = auto()
    MODEL_DOWNLOAD  = auto()

POLICY_KEY_TO_CAPABILITY: dict[str, Capability] = {
    "allow_network":           Capability.NETWORK,
    "allow_filesystem_write":  Capability.FILESYSTEM_WRITE,
    "allow_shell":             Capability.SHELL,
    "allow_email":             Capability.EMAIL_SEND,
    "allow_calendar":          Capability.CALENDAR_WRITE,
    "allow_payment":           Capability.PAYMENT_EXECUTE,
    "allow_memory_persist":    Capability.MEMORY_WRITE,
}
