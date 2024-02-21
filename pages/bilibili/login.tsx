import axios from 'axios';
import Head from 'next/head';
import Script from 'next/script';
import { useQRCode } from 'next-qrcode';
import { useState, useEffect } from 'react';

type Geetest = {
    gt: string,
    challenge: string
}

type CaptchaResult = {
    geetest_validate: string,
    geetest_seccode: string,
}

export default function Home() {
    const [url, setUrl] = useState(' ');
    let key: string;
    let timer: NodeJS.Timer;

    const { Canvas } = useQRCode();

    useEffect(() => {
        loadQR();
        timer = setInterval(() => pull(), 2000);
    }, [])

    function loadQR() {
        axios.get('/api/bilibili/qr').then(response => {
            if (response.status != 200) {
                console.error(response.data);
                return;
            }
            const { url, qrcode_key } = response.data;
            console.info(response.data);

            setUrl(url);
            key = qrcode_key;
        });
    }

    async function pull() {
        const response = await axios.get(`/api/bilibili/pull?qrcode_key=${key}`);

        switch (response.data['status']) {
            case 0:
                alert('success!');
                clearInterval(timer);
                break;
            case 86101:
                console.info('wait for scan');
                break;
            case 86090:
                console.info('wait for confirm');
                break;
            case 86038:
                alert('qr outdated! please refresh!');
                clearInterval(timer);
                break;
            default:
                console.warn(`unknown code: ${response.data['status']}`);
        }
    }

    return (
        <>
            <Head>
                <title>Login</title>
            </Head>
            <div>
                <Canvas
                    text={url}
                    options={{
                        errorCorrectionLevel: 'M',
                        margin: 3,
                        scale: 4,
                        width: 200,
                    }} />
            </div>
        </>
    )
}
