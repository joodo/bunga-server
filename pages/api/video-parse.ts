import type { NextApiRequest, NextApiResponse } from 'next'
import axios from 'axios';
import { JSDOM } from 'jsdom';

class NeedEpisodeError extends Error {
    public constructor(public epNames: Array<string>) {
        super('Need episode index');
    }
}

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.method == 'OPTIONS') {
        return res.status(200).json({
            supports: [
                { name: '小宝影院', url: 'https://xbyy.cc/' },
                { name: '蛋蛋赞', url: 'https://www.dandanzan.in/' },
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

        try {
            switch (url.host) {
                case 'xbyy.cc':
                    return res.status(200).json(await parseXiaoBao(url));
                case 'www.dandanzan.in':
                    return res.status(200).json(await parseDandanzan(url));
                default:
                    return res.status(400).json('unsupported site.');
            }
        } catch (e) {
            if (e instanceof NeedEpisodeError) {
                return res.status(418).json({
                    'message': e.message,
                    'episodes': e.epNames,
                });
            } else if (e instanceof Error) {
                return res.status(400).json({
                    'message': e.message,
                });
            } else {
                return res.status(400).json({
                    'message': 'unknown error',
                });
            }
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
        image: `https://xbyy.cc/poster/${videoId}.jpg`,
    };
}

async function parseDandanzan(url: URL) {
    let response = await axios.get(url.toString());
    const { document } = (new JSDOM(response.data)).window;

    const epElementList = Array.from(document.querySelectorAll('li.play-btn')).reverse();

    const ep = url.searchParams.get('ep');
    if (!ep) {
        throw new NeedEpisodeError(epElementList.map(e => e.textContent!));
    }

    const videoId = url.pathname.split('/').pop() as String;

    const epElement = epElementList[parseInt(ep)];
    const epValue = epElement.getAttribute('ep_slug');
    response = await axios.get(`https://www.dandanzan.in/ddp/${videoId}-${epValue}`);
    const videos = response.data['video_plays'].map((e: { play_data: String; }) => e.play_data);


    const epTitle = epElement.textContent!;
    const videoName = document.querySelector('meta[name=keywords]')?.getAttribute('content')?.split(',')[0];
    const title = `${videoName} - ${epTitle}`;

    return {
        title,
        videos,
        image: `https://www.dandanzan.in/cover/${videoId}.jpg`,
    };
}
