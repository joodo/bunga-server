import type { NextApiRequest, NextApiResponse } from 'next'
import axios from 'axios';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.method != 'GET') return res.status(405).json('Only get allowed.');

    try {
        const alistToken = req.headers['alist-token'];
        const alistHost = process.env.ALIST_HOST + 'fs/get';
        const alistPath = decodeURI(req.query['path'] as string);

        const infoReq = await axios.post(
            alistHost,
            { path: alistPath }, {
            headers: {
                'Authorization': alistToken,
                'Content-Type': 'application/json',
            },
        });

        const imageReq = await axios.get(
            infoReq.data.data.thumb,
            { responseType: 'arraybuffer' },
        );
        const imageData = Buffer.from(imageReq.data, 'binary');
        return res
            .status(200)
            .setHeader('Content-Type', 'image/jpg')
            .send(imageData);
    } catch (e) {
        return res.status(500).json({ 'message': e });
    }
}