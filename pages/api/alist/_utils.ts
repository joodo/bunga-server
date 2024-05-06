import axios from 'axios';

export async function getToken(): Promise<string> {
    const host = process.env.ALIST_HOST!;
    const username = process.env.ALIST_USERNAME;
    const password = process.env.ALIST_PASSWORD;

    const response = await axios.post(host + 'auth/login', { username, password });

    const code = response.data['code'];
    if (code != 200) throw new Error(response.data['message']);

    return response.data['data']['token'];
}