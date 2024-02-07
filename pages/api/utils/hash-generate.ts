import type { NextApiRequest, NextApiResponse } from 'next'
import { md5 } from 'js-md5';
import { sql } from "@vercel/postgres";

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    try {
        switch (req.method) {
            case 'POST': {
                console.log(req.body['text']);
                const text = req.body['text'];
                const hash = md5.base64(text).replaceAll('=', '');
                await sql`INSERT INTO hash_string (hash, text) VALUES (${hash}, ${text});`;
                return res.status(201).json({
                    message: 'success',
                    data: { hash, message: text },
                });
            }
            case 'GET': {
                const hash = req.query['hash']?.toString();
                if (!hash) throw '"hash" query is needed.';

                const { rows } = await sql`SELECT * FROM hash_string WHERE hash=${hash}`;
                if (rows.length == 0) throw 'No record found.';

                return res.status(200).json({
                    message: 'success',
                    data: rows[0],
                });
            }
            default: throw ('Method not allowed');
        }
    } catch (err) {
        if (err instanceof Error) {
            return res.status(400).json({ "message": err.message });
        }
    }
}

var makeCRCTable = function () {
    var c;
    var crcTable = [];
    for (var n = 0; n < 256; n++) {
        c = n;
        for (var k = 0; k < 8; k++) {
            c = ((c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1));
        }
        crcTable[n] = c;
    }
    return crcTable;
}
