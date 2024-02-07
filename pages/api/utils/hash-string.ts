import type { NextApiRequest, NextApiResponse } from 'next'
import { sql } from "@vercel/postgres";

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    try {
        switch (req.method) {
            case 'POST': {
                const text = req.body['text'];
                const hash = req.body['hash'];
                if (!text || !hash) throw '"hash" and "text" field are needed.';

                await sql`INSERT INTO hash_string (hash, text) VALUES (${hash}, ${text});`;
                return res.status(201).json({
                    message: 'success',
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
