import random
from django.http import JsonResponse
from django.db import models
import requests

from .tls_sig_api import TLSSigAPIv2


def generate_user_sig(tencent_config: models.Model):
    api = TLSSigAPIv2(tencent_config.tencent_app_id,
                      tencent_config.tencent_app_key)
    return api.genUserSig(tencent_config.tencent_admin_name)


def request(
    tencent_config: models.Model,
    api: str,
    payload: dict = {},
) -> dict:
    host = 'console.tim.qq.com'
    user_sig = generate_user_sig(tencent_config)
    random_number = random.randint(0, 4294967295)

    url = (
        f'https://{host}/v4/{api}?'
        f'sdkappid={tencent_config.tencent_app_id}&'
        f'identifier={tencent_config.tencent_admin_name}&'
        f'usersig={user_sig}&'
        f'random={random_number}&'
        f'contenttype=json'
    )
    response = requests.post(url, json=payload)
    return response.json()
