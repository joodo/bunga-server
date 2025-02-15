user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0'


def parse_set_cookie(set_cookie):
    result = {}
    for item in set_cookie.split(','):
        item = item.split(';')[0].strip()
        if not item:
            continue
        if '=' not in item:
            continue
        name, value = item.split('=', 1)
        result[name] = value
    return result
