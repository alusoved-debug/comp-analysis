import os
import json
import uuid
import traceback

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file
import anthropic

from analyzer import FaultAnalyzer
from local_chat import answer as local_answer

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

_cache: dict = {}

SYSTEM_BASE = """אתה מומחה לניתוח תקלות, FRACAS וניהול איכות (AS9100 Rev D).
אתה עוזר למהנדסי איכות ומנהלים להבין נתוני תקלות, לזהות מגמות,
לקבוע סיבות שורש ולהגדיר פעולות מתקנות.

כשיש נתוני ניתוח — ענה על סמך הנתונים בפועל, עם מספרים ספציפיים.
כשאין קובץ — ענה על שאלות כלליות בנושא FRACAS, RCA ואיכות.
היה תמציתי, מקצועי ומעשי. השתמש בנקודות תבליט כשמתאים.
כשמדובר בציות AS9100 — ציין את הסעיף הרלוונטי.
ענה תמיד בעברית, אלא אם המשתמש כותב בשפה אחרת."""


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/sample')
def sample():
    sample_path = os.path.join(os.path.dirname(__file__), 'AI_unclassified.xlsx')
    if not os.path.isfile(sample_path):
        return jsonify({'error': 'קובץ דוגמה לא נמצא'}), 404
    return send_file(
        sample_path,
        as_attachment=True,
        download_name='דוגמה_תקלות.xlsx',
    )


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'לא נבחר קובץ'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'שם קובץ ריק'}), 400
    if not f.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'יש להעלות קובץ Excel (.xlsx או .xls)'}), 400

    sid = str(uuid.uuid4())[:8]
    fpath = os.path.join(UPLOAD_DIR, f'upload_{sid}.xlsx')
    f.save(fpath)

    try:
        analysis = FaultAnalyzer(fpath).analyze()
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'לא ניתן לקרוא את הקובץ: {str(e)}'}), 422

    _cache[sid] = {
        'filepath': fpath,
        'analysis': analysis,
        'filename': f.filename,
    }

    return jsonify({'session_id': sid, 'analysis': analysis})


@app.route('/api/status')
def status():
    key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    return jsonify({
        'api_configured': bool(key and key != 'your-api-key-here'),
        'mode': 'ai' if key and key != 'your-api-key-here' else 'local',
    })


@app.route('/chat', methods=['POST'])
def chat():
    body = request.json or {}
    sid = body.get('session_id', '')
    message = body.get('message', '').strip()
    history = body.get('history', [])

    if not message:
        return jsonify({'error': 'הודעה ריקה'}), 400

    analysis = _cache[sid]['analysis'] if sid and sid in _cache else None
    api_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()

    if not api_key or api_key == 'your-api-key-here':
        return jsonify({
            'response': local_answer(message, analysis),
            'mode': 'local',
        })

    if sid and sid in _cache:
        analysis = _cache[sid]['analysis']
        fname = _cache[sid]['filename']
        ctx = (
            f"\n\nהמשתמש העלה קובץ Excel: '{fname}'.\n"
            f"תוצאות הניתוח (JSON):\n{json.dumps(analysis, ensure_ascii=False, indent=2)}\n\n"
            "התייחס למספרים ספציפיים מהנתונים כשזה רלוונטי."
        )
        system = SYSTEM_BASE + ctx
    else:
        system = SYSTEM_BASE + "\n\nעדיין לא הועלה קובץ — ענה על שאלות כלליות בנושא תקלות ואיכות."

    clean_history = []
    for turn in history[-20:]:
        if turn.get('role') in ('user', 'assistant') and turn.get('content'):
            clean_history.append({'role': turn['role'], 'content': turn['content']})

    messages = clean_history + [{'role': 'user', 'content': message}]

    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1500,
            system=system,
            messages=messages,
        )
        return jsonify({'response': resp.content[0].text, 'mode': 'ai'})
    except anthropic.AuthenticationError:
        return jsonify({'error': 'מפתח API לא תקין. בדוק את ANTHROPIC_API_KEY'}), 401
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'שגיאה בשירות AI: {str(e)}'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=True, port=port)
