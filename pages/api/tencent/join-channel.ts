import type { NextApiRequest, NextApiResponse } from 'next'
import axios from 'axios';
import { getRequestUrl, fetchGroupData } from './_utils';


export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    if (req.method != 'POST') return res.status(405).json('Only post allowed.');
    const userId = req.body['user_id'];
    const joinGroupId = req.body['id'];
    const joinGroupData = req.body['data'];

    if (joinGroupData) {
        let groupId;
        for (let suffix = 0; true; suffix++) {
            groupId = suffix == 0 ? joinGroupData['hash'] : `${joinGroupData['hash']}-${suffix}`;
            let response = await axios.post(
                getRequestUrl('create_group'),
                {
                    'Type': 'Private',
                    'GroupId': groupId,
                    'Name': joinGroupData['name'],
                    'FaceUrl': JSON.stringify(joinGroupData['image']),
                    'MemberList': [{ 'Member_Account': userId }],
                    'AppDefinedData': [
                        { 'Key': 'sharer', 'Value': JSON.stringify(joinGroupData['sharer']) },
                        { 'Key': 'video_type', 'Value': JSON.stringify(joinGroupData['video_type']) },
                        { 'Key': 'video_hash', 'Value': JSON.stringify(joinGroupData['hash']) },
                        { 'Key': 'path', 'Value': JSON.stringify(joinGroupData['path']) },
                    ],
                },
            );

            if (response.data['ErrorCode'] === 0) {
                // Create success
                return res.status(200).json({
                    'id': groupId,
                    'data': joinGroupData,
                });
            } else if (response.data['ErrorCode'] === 10021) {
                // Group exist
                const groupData = await fetchGroupData(groupId);
                if (groupData['hash'] === joinGroupData['hash']) {
                    await inviteUser(userId, groupId);
                    return res.status(200).json({
                        'id': groupId,
                        'data': groupData,
                    });
                }
            } else {
                return res.status(500).json(response.data);
            }
        }
    } else if (joinGroupId) {
        await inviteUser(userId, joinGroupId);
        const groupData = await fetchGroupData(joinGroupId);
        return res.status(200).json({
            'id': joinGroupId,
            'data': groupData,
        });
    } else {
        return res.status(400).json('id or data field required');
    }
}

function inviteUser(userId: string, groupId: string): Promise<void> {
    return axios.post(
        getRequestUrl('add_group_member'),
        {
            'GroupId': groupId,
            'MemberList': [{ 'Member_Account': userId }],
        }
    );
}
