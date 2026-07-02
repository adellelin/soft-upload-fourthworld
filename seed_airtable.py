"""Run once to seed Airtable with initial collective fragments."""
import json
import os
import urllib.request

AIRTABLE_TOKEN    = os.environ.get('AIRTABLE_TOKEN', '')
AIRTABLE_BASE_ID  = os.environ.get('AIRTABLE_BASE_ID', '')
AIRTABLE_TABLE_ID = os.environ.get('AIRTABLE_TABLE_ID', '')

SEEDS = [
    "I came looking for something I couldn't name",
    "to remember what community feels like in my body",
    "the way strangers can become kin",
    "I arrived carrying grief and looking for somewhere to set it down",
    "to be witnessed and to witness others",
    "something that won't last and matters anyway",
    "the feeling of belonging before you've earned it",
    "to awaken my body and heal my mind",
    "witnessing the beauty in others without wanting to own it",
    "a vibe that needs to be absorbed and shared",
    "releasing doubt and welcoming change",
    "knowing how to flow into unexpected circumstances",
    "realizing I've survived hardships and can help others",
    "giving myself permission to let go and change",
]

def write(fragment):
    url  = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
    body = json.dumps({'fields': {
        'session_id':      f'seed-{SEEDS.index(fragment):02d}',
        'public_fragment': fragment,
    }}).encode()
    req  = urllib.request.Request(url, data=body, method='POST', headers={
        'Authorization': f'Bearer {AIRTABLE_TOKEN}',
        'Content-Type':  'application/json',
    })
    with urllib.request.urlopen(req) as res:
        print(f"OK: {fragment[:50]}")

if __name__ == '__main__':
    if not all([AIRTABLE_TOKEN, AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID]):
        print("Set AIRTABLE_TOKEN, AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID env vars first")
    else:
        for s in SEEDS:
            write(s)
