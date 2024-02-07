import type { NextApiRequest, NextApiResponse } from 'next'
import axios from 'axios';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.method != 'GET') return res.status(405).json('Only get allowed.');

    const host = process.env.ALIST_HOST!;
    const username = process.env.ALIST_USERNAME;
    const password = process.env.ALIST_PASSWORD;
    console.log(host);
    const response = await axios.post(host + 'auth/login', { username, password });

    const code = response.data['code'];
    if (code != 200) return res.status(code).json({ 'message': response.data['message'] });

    return res.status(200).json({
        host,
        token: response.data['data']['token'],
    });
}
