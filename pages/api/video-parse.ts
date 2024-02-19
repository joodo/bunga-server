import type { NextApiRequest, NextApiResponse } from 'next'
import axios from 'axios';
import { JSDOM } from 'jsdom';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.method == 'OPTIONS') {
        return res.status(200).json({
            supports: [
                {
                    name: '小宝影院',
                    url: 'https://xbyy.cc/',
                }
            ],
        });
    }

    if (req.method == 'POST') {

        let url: URL;
        try {
            url = new URL(req.body.url);
        } catch {
            return res.status(400).json('url invalid.');
        }

        switch (url.host) {
            case 'xbyy.cc':
                return res.status(200).json(await parseXiaoBao(url));
            default:
                return res.status(400).json('unsupported site.');
        }

    }

    return res.status(405).json('method not allowed.');
}

async function parseXiaoBao(url: URL) {
    const filename = url.pathname.split('/').pop() as String;
    const split = filename.split(/-|\./);

    const videoId = split[0];
    const ep = url.searchParams.get('ep_slug') ?? split[1];

    const result = await Promise.all([
        axios.get(`https://xbyy.cc/_lazy_plays/${videoId}/${ep}`)
            .then(response => response.data['video_plays'].map((e: { play_data: String; }) => e.play_data)),
        axios.get(url.toString())
            .then(response => {
                const { document } = (new JSDOM(response.data)).window;
                return document.querySelector('h1.h3')?.textContent?.replaceAll('\n', ' ');
            }),
    ]);

    const [videos, title] = result;

    return {
        title,
        videos,
        path: url.toString(),
        image: `https://xbyy.cc/poster/${videoId}.jpg`,
    };
}
