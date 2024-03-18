import type { NextApiRequest, NextApiResponse } from 'next'
import { StreamChat } from 'stream-chat';

import { getSess } from '../bilibili/sess';
import { getAList } from './alist';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    // Register user
    if (req.method != 'POST') return res.status(405).json('Only post allowed.');

    const api_key = process.env.STEAMIO_KEY!;
    const api_secret = process.env.STEAMIO_SECRET;
    const serverClient = StreamChat.getInstance(api_key, api_secret);

    const user_id = req.body.user_id;
    if (!user_id) return res.status(400).json('user_id field is required.');
    const user_token = serverClient.createToken(user_id);

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
        stream_io: {
            app_key: process.env.STEAMIO_KEY!,
            user_token,
        },
        agora: process.env.AGORA_KEY!,
        bilibili_sess,
        alist,
    });
}
