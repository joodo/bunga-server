import { RtcRole, RtcTokenBuilder } from 'agora-token';
import type { NextApiRequest, NextApiResponse } from 'next'

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.method != 'POST') return res.status(405).json('Only post allowed.');

    const { uid, channel } = req.body;
    const { AGORA_CERTIFICATION, AGORA_KEY } = process.env;

    const token = RtcTokenBuilder.buildTokenWithUid(
        AGORA_KEY!,
        AGORA_CERTIFICATION!,
        channel,
        uid,
        RtcRole.PUBLISHER,
        86400,
        86400,
    );
    return res.status(200).json({ token });
}