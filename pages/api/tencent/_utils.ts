import { Api } from './_tencent_usersig.js'
import axios from 'axios';

export type ChannelData = {
    'name': string,
    'image': string | null,
    'video_type': string,
    'hash': string,
    'created_at': number,
    'path': string | null,
    'sharer': {
        id: string,
        name: string,
        color_hue: number | null,
    },
}

export async function fetchGroupDatas(groupIds: Array<String>): Promise<Array<{ id: string, data: ChannelData }>> {
    if (groupIds.length === 0) return [];

    const response = await axios.post(
        getRequestUrl('get_group_info'),
        { 'GroupIdList': groupIds },
    );

    return response.data['GroupInfo'].map(
        (info: {
            CreateTime: number;
            GroupId: string;
            Introduction: string;
            FaceUrl: string;
            AppDefinedData: Array<{ Key: string; Value: string; }>;
        }) => {
            const customFields = info.AppDefinedData.reduce(
                (map: { [x: string]: any; }, element: { Key: string; Value: string; }) => {
                    map[element.Key] = JSON.parse(element.Value);
                    return map;
                },
                {},
            );
            return {
                id: info.GroupId,
                data: {
                    'name': info.Introduction,
                    'image': JSON.parse(info.FaceUrl),
                    'created_at': info.CreateTime,
                    'video_type': customFields['video_type'],
                    'hash': customFields['video_hash'],
                    'path': customFields['path'],
                    'sharer': customFields['sharer'],
                },
            };
        },
    );
}

export function fetchGroupData(groupId: string): Promise<ChannelData> {
    return fetchGroupDatas([groupId]).then(groups => groups[0].data);
}

export function createUserSig(userId: string): string {
    const serverClient = new Api(
        process.env.TENCENT_APPID,
        process.env.TENCENT_KEY,
    );
    return serverClient.genUserSig(userId, 5184000);
}

export function getRequestUrl(api: string): string {
    const appId = process.env.TENCENT_APPID;
    const adminName = process.env.TENCENT_ADMIN_NAME!;
    const adminSig = createUserSig(adminName);
    return `https://console.tim.qq.com/v4/group_open_http_svc/${api}?sdkappid=${appId}&identifier=${adminName}&usersig=${adminSig}&random=1&contenttype=json`;
}