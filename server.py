import http.server
import json
import os
import random
import threading
import urllib.request
import urllib.error
import urllib.parse
import uuid
from datetime import datetime

PORT               = int(os.environ.get('PORT', 8767))
CLAUDE_API_KEY     = os.environ.get('CLAUDE_API_KEY', '')
AIRTABLE_TOKEN     = os.environ.get('AIRTABLE_TOKEN', '')
AIRTABLE_BASE_ID   = os.environ.get('AIRTABLE_BASE_ID', '')
AIRTABLE_TABLE_ID  = os.environ.get('AIRTABLE_TABLE_ID', '')

SEED_FRAGMENTS = [
    "I came looking for something I couldn't name",
    "To remember what community feels like in my body",
    "I want to preserve the way strangers can become kin",
    "Hoping to release what no longer serves the collective",
    "I arrived carrying grief and looking for somewhere to set it down",
    "To be witnessed and to witness others",
    "The feeling of building something together that won't last and matters anyway",
]


# ── Claude ────────────────────────────────────────────────────────────────
def claude_call(prompt, system=None, max_tokens=400):
    body = {
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    if system:
        body['system'] = system
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=json.dumps(body).encode(),
        headers={
            'Content-Type': 'application/json',
            'x-api-key': CLAUDE_API_KEY,
            'anthropic-version': '2023-06-01',
        }
    )
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read())['content'][0]['text'].strip()


def extract_fragment(answers):
    why       = answers.get('why_are_you_here', '')
    community = answers.get('sustainable_community', '')
    prompt = (
        f"Two responses from a participant at a community gathering:\n\n"
        f"Why they are here: \"{why}\"\n"
        f"What they wish to preserve: \"{community}\"\n\n"
        "Extract ONE short fragment (5–15 words) from either response that:\n"
        "- Comes directly from their words, not invented\n"
        "- Is the most resonant or unexpected phrase\n"
        "- Could float alone and still carry meaning\n"
        "Return ONLY the fragment, no explanation, no punctuation at the end."
    )
    try:
        return claude_call(prompt, max_tokens=50)
    except Exception as e:
        print(f"Fragment extraction error: {e}")
        return ''


# ── Airtable ──────────────────────────────────────────────────────────────
def airtable_request(method, path, data=None):
    url  = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}{path}"
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(url, data=body, method=method, headers={
        'Authorization': f'Bearer {AIRTABLE_TOKEN}',
        'Content-Type':  'application/json',
    })
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read())


def airtable_write(record):
    try:
        airtable_request('POST', '', {'fields': record})
        print(f"Airtable record written: {record.get('session_id', '')}")
    except Exception as e:
        print(f"Airtable write error: {e}")


def get_returned_fragment():
    try:
        params = urllib.parse.urlencode({
            'fields[]': 'public_fragment',
            'filterByFormula': "NOT({public_fragment} = '')",
            'maxRecords': 100,
        })
        result    = airtable_request('GET', f'?{params}')
        fragments = [
            r['fields']['public_fragment']
            for r in result.get('records', [])
            if r.get('fields', {}).get('public_fragment')
        ]
        if fragments:
            return random.choice(fragments)
    except Exception as e:
        print(f"Airtable read error: {e}")
    return random.choice(SEED_FRAGMENTS)


# ── Batch sync (offline → online) ─────────────────────────────────────────
def process_batch(sessions):
    """Write a batch of sessions from the offline app to Airtable.
    Uses Claude to extract a public_fragment for each session."""
    for s in sessions:
        session_id = s.get('session_id') or str(uuid.uuid4())[:8]
        fragment   = extract_fragment(s) if CLAUDE_API_KEY else s.get('public_fragment', '')
        airtable_write({
            'session_id':            session_id,
            'timestamp':             s.get('timestamp', datetime.utcnow().isoformat()),
            'why_are_you_here':      s.get('why_are_you_here', ''),
            'self_transformation':   s.get('self_transformation', ''),
            'sustainable_community': s.get('sustainable_community', ''),
            'ritual_text':           s.get('ritual_text', ''),
            'festival_action':       s.get('festival_action', ''),
            'public_fragment':       fragment,
            'returned_fragment':     s.get('returned_fragment', ''),
        })


# ── Request handler ───────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/fragment':
            fragment = get_returned_fragment()
            self._json(200, {'fragment': fragment})
            return
        static_exts = ('.html', '.js', '.css', '.ico', '.png')
        if any(self.path.endswith(e) for e in static_exts) or self.path == '/':
            filename  = 'index.html' if self.path == '/' else self.path.lstrip('/')
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
            if os.path.isfile(file_path):
                ext  = os.path.splitext(file_path)[1]
                mime = {'html': 'text/html', 'js': 'application/javascript', 'css': 'text/css'}.get(ext.lstrip('.'), 'application/octet-stream')
                with open(file_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        try:
            data = json.loads(self.rfile.read(length))
        except Exception:
            self.send_response(400); self._cors(); self.end_headers()
            return

        if self.path == '/batch-sync':
            sessions = data.get('sessions', [])
            if not sessions:
                self._json(400, {'error': 'no sessions'})
                return
            try:
                process_batch(sessions)
                self._json(200, {'accepted': len(sessions)})
            except Exception as e:
                print(f"Batch sync error: {e}")
                self._json(500, {'error': str(e)})

        else:
            self._json(404, {'error': 'not found'})

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")


if __name__ == '__main__':
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"Fourth World PWA server running on port {PORT}")
    server.serve_forever()
