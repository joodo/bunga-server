import type { NextApiRequest, NextApiResponse } from 'next'
import { StreamChat } from 'stream-chat';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.headers['Authorization'] !== `Bearer ${process.env.CRON_SECRET}`) {
        return res.status(401).end('Unauthorized');
    }

    const api_key = process.env.STEAMIO_KEY!;
    const api_secret = process.env.STEAMIO_SECRET;
    const serverClient = StreamChat.getInstance(api_key, api_secret);

    const filter = { last_message_at: { $lte: new Date(Date.now() - 60 * 60 * 1000) } };

    const channels = await serverClient.queryChannels(
        // @ts-ignore
        filter,
        undefined,
        {
            watch: false,
            state: true,
        },
    );

    const deleteCids: string[] = [];
    for (const channel of channels) {
        const result = await channel.query({});
        if (!result.watcher_count) {
            deleteCids.push(channel.cid);
        }
    }
    console.info(`Delete channels: ${deleteCids}`);
    await serverClient.deleteChannels(deleteCids, { hard_delete: true });

    res.status(200).json({ message: 'success' });
}