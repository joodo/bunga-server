# PEP-8


from .RtcTokenBuilder2 import *


def generateToken(appKey: str, appCertificate: str, channelId: str, uid: int) -> str:
    return RtcTokenBuilder.build_token_with_uid(
        appKey,
        appCertificate,
        channelId,
        uid,
        Role_Publisher,
        3600 * 24,
        3600 * 24,
    )


def uidFromName(name: str):
    hash_val = 5381
    for char in name:
        hash_val = ((hash_val << 5) + hash_val) + ord(char)
    return hash_val & 0x7FFFFFFF
