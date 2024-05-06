import type { NextApiRequest, NextApiResponse } from 'next'
import axios from 'axios';
import { unstable_cache } from 'next/cache';
import { getToken } from './_utils';

const thumbCache = unstable_cache(
    (path: string) => fetchThumb(path),
    ['alist-thumb'],
    { revalidate: 86400 },
)

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.method != 'GET') return res.status(405).json('Only get allowed.');

    const path = decodeURI(req.query['path'] as string);
    const imageData = await thumbCache(path);
    return res
        .status(200)
        .setHeader('Content-Type', 'image/jpg')
        .send(Buffer.from(imageData, 'binary'));
}

async function fetchThumb(path: string) {
    const alistHost = process.env.ALIST_HOST + 'fs/get';

    const infoReq = await axios.post(
        alistHost,
        { path }, {
        headers: {
            'Authorization': await getToken(),
            'Content-Type': 'application/json',
        },
    });

    const imageReq = await axios.get(
        infoReq.data.data.thumb,
        { responseType: 'arraybuffer' },
    );
    return imageReq.data;
}