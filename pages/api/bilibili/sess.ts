import type { NextApiRequest, NextApiResponse } from 'next'
import { kv } from '@vercel/kv';
import { JSDOM } from 'jsdom';
import axios from 'axios';
import querystring from 'querystring';

type BiliHash = {
    SESSDATA: string,
    bili_jct: string,
    refresh_token: string,
}

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    try {
        return res.status(200).json(getSess());
    } catch (err) {
        if (err instanceof Error) {
            res.status(400).json(err.message);
        }
    }
}

export async function getSess(): Promise<string> {
    const cookies = await kv.hgetall('bilibili_cookies') as BiliHash;
    const sess = cookies.SESSDATA;

    const response = await axios.get(
        'https://passport.bilibili.com/x/passport-login/web/cookie/info',
        { headers: { 'Cookie': `SESSDATA=${sess}` } },
    );
    if (response.data['code'] != 0) {
        console.error(`failed to check cookie with sess ${sess}: ${JSON.stringify(response.data)}`);
        throw new Error('Failed to check cookie outdate.');
    }


    if (response.data.data.refresh) {
        // SESS out of date
        console.info('sess outdated.');
        const newSess = await updateCookie(cookies);
        return newSess;
    } else {
        return sess;
    }
}

async function updateCookie(cookies: BiliHash): Promise<string> {
    const correspondPath = await getCorrespondPath();
    const csrf = await getRefreshCsrf(cookies.SESSDATA, correspondPath);

    const newCookies = await getNewCookies(cookies, csrf);
    console.info(`new cookie info: ${JSON.stringify(newCookies)}`);

    await confirmNewCookies(cookies, newCookies);
    await kv.hset('bilibili_cookies', newCookies);

    return newCookies.SESSDATA;
}

async function getCorrespondPath(): Promise<string> {
    const publicKey = await crypto.subtle.importKey(
        "jwk",
        {
            kty: "RSA",
            n: "y4HdjgJHBlbaBN04VERG4qNBIFHP6a3GozCl75AihQloSWCXC5HDNgyinEnhaQ_4-gaMud_GF50elYXLlCToR9se9Z8z433U3KjM-3Yx7ptKkmQNAMggQwAVKgq3zYAoidNEWuxpkY_mAitTSRLnsJW-NCTa0bqBFF6Wm1MxgfE",
            e: "AQAB",
        },
        { name: "RSA-OAEP", hash: "SHA-256" },
        true,
        ["encrypt"],
    )

    const data = new TextEncoder().encode(`refresh_${Date.now()}`);
    const encrypted = new Uint8Array(await crypto.subtle.encrypt({ name: "RSA-OAEP" }, publicKey, data))
    return encrypted.reduce((str, c) => str + c.toString(16).padStart(2, "0"), "")
}

async function getRefreshCsrf(sess: string, correspondPath: string): Promise<string> {
    const url = `https://www.bilibili.com/correspond/1/${correspondPath}`;
    const response = await axios.get(url, { headers: { 'Cookie': `SESSDATA=${sess}` } });
    if (response.status != 200) {
        console.error(`failed to get csrf with correspondPath ${correspondPath}: response code ${response.status}`);
        throw new Error('Failed to check cookie outdate.');
    }

    const dom = new JSDOM(response.data, { runScripts: "dangerously" });
    const csrf = dom.window.document.evaluate(
        "//div[@id='1-name']/text()",
        dom.window.document,
        null,
        dom.window.XPathResult.STRING_TYPE,
        null,
    ).stringValue;
    return csrf;
}

async function getNewCookies(oldCookies: BiliHash, refresh_csrf: string): Promise<BiliHash> {
    const payload = {
        csrf: oldCookies.bili_jct,
        refresh_csrf,
        source: 'main_web',
        refresh_token: oldCookies.refresh_token,
    };
    const response = await axios.post(
        'https://passport.bilibili.com/x/passport-login/web/cookie/refresh',
        querystring.stringify(payload),
        { headers: { 'Cookie': `SESSDATA=${oldCookies.SESSDATA}` } },
    );
    if (response.data['code'] != 0) {
        console.error(`failed to update cookie with sess ${oldCookies.SESSDATA}, bili_jct ${oldCookies.bili_jct}, refresh_token ${oldCookies.refresh_token}, csrf ${refresh_csrf}: ${JSON.stringify(response.data)}`);
        throw new Error('Failed to update cookie.');
    }

    const { refresh_token } = response.data['data'];
    const m = parseSetCookie(response.headers['set-cookie'] as string[]);
    return {
        SESSDATA: m.get('SESSDATA')!,
        bili_jct: m.get('bili_jct')!,
        refresh_token,
    };
}

function parseSetCookie(headers: string[]): Map<string, string> {
    let re = new Map();
    headers.map(e => {
        const record = e.split(';')[0].split('=');
        re.set(record[0], record[1]);
    });
    return re;
}

async function confirmNewCookies(oldCookies: BiliHash, newCookies: BiliHash): Promise<void> {
    const payload = {
        csrf: newCookies.bili_jct,
        refresh_token: oldCookies.refresh_token,
    };
    const response = await axios.post(
        'https://passport.bilibili.com/x/passport-login/web/confirm/refresh',
        querystring.stringify(payload),
        { headers: { 'Cookie': `SESSDATA=${newCookies.SESSDATA}` } },
    );
    if (response.data['code'] != 0) {
        console.error(`failed to confirm new cookie: ${JSON.stringify(response.data)}`);
        throw new Error('Failed to confirm new cookie.');
    }
}
