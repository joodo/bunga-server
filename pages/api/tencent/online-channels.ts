import type { NextApiRequest, NextApiResponse } from 'next'
import axios from 'axios';
import { kv } from '@vercel/kv';
import { ChannelData, fetchGroupDatas, getRequestUrl } from './_utils';

type OnlineChannelCache = {
    timestamp: number,
    channels: Array<{
        id: string,
        data: ChannelData,
    }>,
}

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.method != 'GET') return res.status(405).json('Only get allowed.');

    const onlineChannelCache = await kv.hgetall('online_channel_cache') as OnlineChannelCache | null;
    if (onlineChannelCache && Date.now() - onlineChannelCache.timestamp < 3000) {
        return res.status(200).json({ channels: onlineChannelCache.channels });
    }

    const response = await axios.post(getRequestUrl('get_appid_group_list'), {});
    const groupIds = response.data['GroupIdList'].map((e: { GroupId: string; }) => e.GroupId);

    const channels = (await fetchGroupDatas(groupIds))
        .filter(channel => channel.data.video_type === 'online');
    await kv.hset('online_channel_cache', {
        timestamp: Date.now(),
        channels,
    });
    return res.status(200).json(channels);
}