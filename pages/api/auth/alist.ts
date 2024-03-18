import type { NextApiRequest, NextApiResponse } from 'next'
import axios from 'axios';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.method != 'GET') return res.status(405).json('Only get allowed.');

    try {
        const result = await getAList();
        return res.status(200).json(result);
    } catch (e) {
        return res.status(400).json({ 'message': e });
    }
}

export async function getAList() {
    const host = process.env.ALIST_HOST!;
    const username = process.env.ALIST_USERNAME;
    const password = process.env.ALIST_PASSWORD;

    const response = await axios.post(host + 'auth/login', { username, password });

    const code = response.data['code'];
    if (code != 200) throw new Error(response.data['message']);

    return {
        host,
        token: response.data['data']['token'],
    };
}
