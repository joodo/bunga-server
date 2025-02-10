import binascii
import requests
import time

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from lxml.html import soupparser

from server.models import BilibiliAccount
from . import user_agent, parse_set_cookie

# see https://github.com/SocialSisterYi/bilibili-API-collect/blob/e5fbfed42807605115c6a9b96447f6328ca263c5/docs/login/cookie_refresh.md


def keep_sess_fresh(instance: BilibiliAccount) -> bool:
    # check fresh
    response = requests.get(
        'https://passport.bilibili.com/x/passport-login/web/cookie/info',
        cookies={'SESSDATA': instance.sess},
        headers={'User-Agent': user_agent},
    )
    if not response.ok:
        return False

    data = response.json()
    if data['code'] != 0:
        return False
    if not data['data']['refresh']:
        return True

    # correspond_path
    ts = round(time.time() * 1000)
    key = RSA.importKey('''\
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDLgd2OAkcGVtoE3ThUREbio0Eg
Uc/prcajMKXvkCKFCWhJYJcLkcM2DKKcSeFpD/j6Boy538YXnR6VhcuUJOhH2x71
nzPjfdTcqMz7djHum0qSZA0AyCBDABUqCrfNgCiJ00Ra7GmRj+YCK1NJEuewlb40
JNrRuoEUXpabUzGB8QIDAQAB
-----END PUBLIC KEY-----''')
    cipher = PKCS1_OAEP.new(key, SHA256)
    encrypted = cipher.encrypt(f'refresh_{ts}'.encode())
    correspond_path = binascii.b2a_hex(encrypted).decode()

    # csrf
    response = requests.get(
        f'https://www.bilibili.com/correspond/1/{correspond_path}',
        cookies={'SESSDATA': instance.sess},
        headers={'User-Agent': user_agent},
    )
    if not response.ok:
        return False
    tree = soupparser.fromstring(response.text)
    matches = tree.xpath("//div[@id='1-name']/text()")
    csrf = matches[0]

    # new cookies
    response = requests.post(
        'https://passport.bilibili.com/x/passport-login/web/cookie/refresh',
        {
            'csrf': instance.bili_jct,
            'refresh_csrf': csrf,
            'source': 'main_web',
            'refresh_token': instance.refresh_token,
        },
        cookies={'SESSDATA': instance.sess},
        headers={'User-Agent': user_agent},
    )
    if not response.ok:
        return False

    data = response.json()
    if data['code'] != 0:
        return False

    cookies = parse_set_cookie(response.headers['set-cookie'])
    instance.sess = cookies['SESSDATA']
    instance.bili_jct = cookies['bili_jct']
    instance.refresh_token = data['data']['refresh_token']
    instance.save()
    return True
