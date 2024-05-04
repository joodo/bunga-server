import type { NextApiRequest, NextApiResponse } from 'next'
import { StreamChat } from 'stream-chat';

import { getSess } from '../bilibili/sess';
import { getAList } from './alist';
import { createUserSig } from '../tencent/_utils';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.method != 'POST') return res.status(405).json('Only post allowed.');

    // Chat
    const userId = req.body.user_id;
    if (!userId) return res.status(400).json('user_id field is required.');
    const chat = getChatInfo(userId);

    // Bilibili sess
    let bilibili_sess;
    try {
        bilibili_sess = await getSess();
    } catch (e) {
        console.error(e);
        bilibili_sess = null;
    }

    // AList
    let alist;
    try {
        alist = await getAList();
    } catch (e) {
        console.error(e);
        alist = null;
    }

    res.status(200).json({
        chat,
        voice_call: {
            service: 'agora',
            key: process.env.AGORA_KEY!,
        },
        bilibili_sess,
        alist,
    });
}

function getChatInfo(userId: string) {
    switch (process.env.CHAT_SERVICE) {
        case 'stream_io': return getStreamIOInfo(userId);
        case 'tencent': return getTencentInfo(userId);
        default: return null;
    }
}

function getStreamIOInfo(userId: string) {
    const api_key = process.env.STEAMIO_KEY!;
    const api_secret = process.env.STEAMIO_SECRET;
    const serverClient = StreamChat.getInstance(api_key, api_secret);

    const user_token = serverClient.createToken(userId);
    return {
        service: 'stream_io',
        app_key: process.env.STEAMIO_KEY!,
        user_token,
    };
}

function getTencentInfo(userId: string) {
    return {
        service: 'tencent',
        app_id: process.env.TENCENT_APPID!,
        user_sig: createUserSig(userId),
    };
}
