import ws from 'k6/ws';
import { check } from 'k6';
import http from 'k6/http';

export const options = {
    vus: 50,
    duration: '30s',
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const WS_URL = __ENV.WS_URL || 'ws://localhost:8005';
const ORG_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

export default function () {
    const loginRes = http.post(`${BASE_URL}/api/v1/auth/login`, JSON.stringify({
        email: 'load-test@voiceai.demo',
        password: 'loadtest123'
    }), {
        headers: { 'Content-Type': 'application/json' },
    });

    let token = '';
    if (loginRes.status === 200) {
        token = loginRes.json('access_token');
    } else {
        token = 'fallback-token-for-testing'; // Typically tests will fail if token is invalid, but k6 will show the metrics
    }

    const url = `${WS_URL}/ws/${ORG_ID}?token=${token}`;

    const res = ws.connect(url, function (socket) {
        socket.on('open', () => {
            socket.setInterval(function timeout() {
                socket.send(JSON.stringify({ type: 'ping' }));
            }, 10000);
        });

        socket.on('message', (data) => {
            // handle messages
        });

        socket.setTimeout(function () {
            socket.close();
        }, 29000);
    });

    check(res, { 'status is 101': (r) => r && r.status === 101 });
}
