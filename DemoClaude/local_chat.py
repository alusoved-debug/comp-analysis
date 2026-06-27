"""Local rule-based chat — no API key required."""


def _bullets(items):
    return '\n'.join(f'• {x}' for x in items)


def _top_list(distribution, n=3):
    if not distribution:
        return []
    return [f"{x['name']} — {x['count']} ({x['percentage']}%)" for x in distribution[:n]]


def _pareto_text(distribution, title):
    if not distribution:
        return f'אין נתונים ל{title}.'
    lines = [f'**{title}** (ניתוח פריטו):', '']
    for i, x in enumerate(distribution[:8], 1):
        zone = '▲ Vital Few' if x['cumulative'] <= 80 else '▼ Useful Many'
        lines.append(f"{i}. {x['name']}: {x['count']} ({x['percentage']}%), מצטבר {x['cumulative']}% — {zone}")
    vital = [x['name'] for x in distribution if x['cumulative'] <= 80]
    if vital:
        lines.append('')
        lines.append(f"**מוקדי טיפול (80% ראשונים):** {_bullets(vital[:5])}")
    return '\n'.join(lines)


def _recommendations_text(analysis):
    recs = analysis.get('recommendations') or []
    if not recs:
        return _legacy_recommendations(analysis)
    lines = ['**המלצות לביצוע:**', '']
    for r in recs[:8]:
        lines.append(f"{r['priority']}. **{r['title']}** [{r['category']}]")
        lines.append(f"   {r['detail']}")
    return '\n'.join(lines)


def _legacy_recommendations(analysis):
    m = analysis.get('metrics', {})
    recs = []
    if m.get('open_items', 0) > 0:
        recs.append(f"טיפול ב-{m['open_items']} פריטים פתוחים — עדיפות לסגירה מהירה")
    if m.get('closure_rate', 100) < 80:
        recs.append(f"שיפור אחוז הסגירה ({m.get('closure_rate')}%) — יעד: 80%+")
    if not recs:
        recs.append('הנתונים נראים תקינים — המשך מעקב חודשי')
    return '**המלצות לפעולה:**\n' + _bullets(recs)


def _root_cause_analysis(analysis):
    causes = analysis.get('root_cause_distribution') or []
    recurring = analysis.get('recurring_causes') or []
    if not causes:
        return 'לא נמצאה עמודת סיבת שורש בקובץ.'

    lines = ['**ניתוח בעיות שורש (RCA):**', '']
    lines.append('**התפלגות סיבות:**')
    for i, c in enumerate(causes[:6], 1):
        lines.append(f"{i}. {c['name']}: {c['count']} ({c['percentage']}%)")

    vital = [c for c in causes if c['cumulative'] <= 80]
    if vital:
        lines.append('')
        lines.append('**גורמי שורש קריטיים (פריטו 80%):**')
        lines.append(_bullets([f"{c['name']} — {c['percentage']}%" for c in vital[:5]]))

    if recurring:
        lines.append('')
        lines.append(f'**סיבות חוזרות ({len(recurring)}):**')
        lines.append(_bullets([f"{r['name']} × {r['count']}" for r in recurring[:5]]))

    lines.append('')
    lines.append('**פעולות מומלצות:**')
    lines.append(f"• חקירת 5 Whys עבור: {causes[0]['name']}")
    lines.append('• עדכון FMEA / תהליך ייצור')
    lines.append('• מעקב אffectiveness לאחר CA')
    return '\n'.join(lines)


def _recurring_faults_text(analysis):
    recurring = analysis.get('recurring_faults') or []
    m = analysis.get('metrics', {})
    if not recurring:
        return '✓ לא זוהו תקלות חוזרות — כל סוג תקלה מופיע פעם אחת בלבד.'

    lines = [
        f"**תקלות חוזרות — {len(recurring)} סוגים**",
        f"(מתוך {m.get('unique_modes', '—')} סוגי תקלה ייחודיים)",
        '',
    ]
    for i, r in enumerate(recurring[:10], 1):
        lines.append(f"{i}. **{r['name']}** — {r['count']} פעמים ({r['percentage']}%)")

    lines.append('')
    lines.append('**המלצה:** תקלות חוזרות מצביעות על כשל מערכתי — נדרש RCA מעמיק ופעולה מתקנת.')
    return '\n'.join(lines)


def _main_problems_text(analysis):
    modes = analysis.get('failure_mode_distribution') or []
    systems = analysis.get('system_distribution') or []
    total = analysis.get('total_failures', 0)

    if not modes and not systems:
        return 'לא זוהו סוגי בעיה בקובץ.'

    lines = [f'**סוג הבעיות העיקריות** (מתוך {total} תקלות):', '']

    if modes:
        lines.append('**לפי סוג תקלה / קוד פגם:**')
        for i, m in enumerate(modes[:5], 1):
            bar = '█' * max(1, int(m['percentage'] / 5))
            lines.append(f"{i}. {m['name']}: {m['count']} ({m['percentage']}%) {bar}")

    if systems:
        lines.append('')
        lines.append('**לפי מערכת / פרויקט / מחלקה:**')
        lines.append(_bullets(_top_list(systems, 5)))

    vital = [m for m in modes if m['cumulative'] <= 80]
    if vital:
        lines.append('')
        lines.append(f"**80% מהתקלות מגיעות מ-{len(vital)} גורמים:**")
        lines.append(_bullets([v['name'] for v in vital[:4]]))

    return '\n'.join(lines)


def _summary_report(analysis):
    m = analysis.get('metrics', {})
    total = analysis.get('total_failures', 0)
    exec_sum = analysis.get('executive_summary') or {}
    recs = analysis.get('recommendations') or []

    lines = [
        '══════════════════════════════',
        '**דוח מסכם — ניתוח תקלות**',
        '══════════════════════════════',
        '',
        f'**סה"כ תקלות:** {total}',
        f"**סגורות / פתוחות:** {m.get('closed_items', '—')} / {m.get('open_items', '—')}",
        f"**אחוז סגירה:** {m.get('closure_rate', '—')}%",
        f"**כיסוי פעולות מתקנות:** {m.get('ca_coverage', '—')}%",
        '',
    ]

    for h in exec_sum.get('highlights') or []:
        lines.append(f'• {h}')

    top_modes = _top_list(analysis.get('failure_mode_distribution'), 3)
    if top_modes:
        lines.append('')
        lines.append('**בעיות עיקריות:**')
        lines.append(_bullets(top_modes))

    top_causes = _top_list(analysis.get('root_cause_distribution'), 3)
    if top_causes:
        lines.append('')
        lines.append('**סיבות שורש מובילות:**')
        lines.append(_bullets(top_causes))

    recurring = analysis.get('recurring_faults') or []
    if recurring:
        lines.append('')
        lines.append(f"**תקלות חוזרות:** {len(recurring)} סוגים")
        lines.append(_bullets([f"{r['name']} × {r['count']}" for r in recurring[:3]]))

    trend = analysis.get('trend_data') or []
    if len(trend) >= 2:
        diff = trend[-1]['count'] - trend[-2]['count']
        direction = 'עלייה' if diff > 0 else 'ירידה' if diff < 0 else 'יציבות'
        lines.append('')
        lines.append(f"**מגמה אחרונה:** {direction} ({abs(diff)} תקלות)")

    if recs:
        lines.append('')
        lines.append('**המלצות לביצוע:**')
        for r in recs[:5]:
            lines.append(f"{r['priority']}. {r['title']}")

    lines.append('')
    lines.append('══════════════════════════════')
    return '\n'.join(lines)


def _general_answer(message):
    msg = message.lower()
    answers = []

    if any(w in msg for w in ['fracas', 'פרקאס']):
        answers.append(
            '**FRACAS** — מערכת דיווח, ניתוח ופעולה מתקנת לתקלות.\n'
            'מחזור: דיווח → ניתוח → RCA → פעולה מתקנת → מעקב → סגירה.'
        )
    if any(w in msg for w in ['rca', 'סיבת שורש', 'שורש', 'בעיות שורש']):
        answers.append(
            '**RCA (Root Cause Analysis)** — שיטות: 5 Whys, דיאגרמת דג, Ishikawa.\n'
            'העלה קובץ Excel לניתוח סיבות שורש מהנתונים.'
        )
    if any(w in msg for w in ['as9100', 'איכות', '9100']):
        answers.append(
            '**AS9100 Rev D** — סעיפים: 8.7, 10.2 (CA), 10.3 (שיפור).'
        )

    if answers:
        return '\n\n'.join(answers)

    return (
        'שלום! העלה קובץ Excel ושאל על:\n'
        '• ניתוח בעיות שורש\n'
        '• תקלות חוזרות\n'
        '• סוג הבעיות העיקריות\n'
        '• המלצות לביצוע\n'
        '• דוח מסכם'
    )


def answer(message, analysis=None):
    msg = message.lower()

    if not analysis:
        return _general_answer(message)

    if any(w in msg for w in ['דוח מסכם', 'דוח', 'מסכם', 'report']):
        return _summary_report(analysis)

    if any(w in msg for w in ['בעיות שורש', 'ניתוח שורש', 'rca', 'root cause']) or (
        'שורש' in msg and any(w in msg for w in ['ניתוח', 'בעי'])
    ):
        return _root_cause_analysis(analysis)

    if any(w in msg for w in ['חוזר', 'recurring', 'חוזרות']):
        return _recurring_faults_text(analysis)

    if any(w in msg for w in ['בעיות עיקר', 'סוג הבעי', 'עיקרי', 'סוגי בעיה', 'סוג הבע']):
        return _main_problems_text(analysis)

    if any(w in msg for w in ['המלצ', 'ביצוע', 'מה לעשות', 'פעול', 'ca', 'מתקנ']):
        return _recommendations_text(analysis)

    m = analysis.get('metrics', {})
    total = analysis.get('total_failures', 0)

    if any(w in msg for w in ['סיכום', 'summary', 'סקירה']):
        return _summary_report(analysis)

    if any(w in msg for w in ['נפוצ', 'מוביל', 'top', '3', 'שלוש']):
        return _main_problems_text(analysis)

    if any(w in msg for w in ['סגיר', 'פתוח', 'closure', 'סטטוס']):
        return (
            f"**מצב סגירה:**\n"
            f"• סה\"כ: {total}\n"
            f"• סגורות: {m.get('closed_items', '—')}\n"
            f"• פתוחות: {m.get('open_items', '—')}\n"
            f"• אחוז סגירה: {m.get('closure_rate', '—')}%"
        )

    if any(w in msg for w in ['פריטו', 'pareto', '80']):
        dist = analysis.get('failure_mode_distribution') or analysis.get('root_cause_distribution')
        title = 'סוגי תקלה' if analysis.get('failure_mode_distribution') else 'סיבות שורש'
        return _pareto_text(dist, title)

    if any(w in msg for w in ['סיב', 'cause', 'שורש']):
        return _root_cause_analysis(analysis)

    if any(w in msg for w in ['מגמ', 'trend', 'חודש']):
        trend = analysis.get('trend_data') or []
        if not trend:
            return 'לא נמצאו נתוני תאריך לניתוח מגמה.'
        lines = ['**מגמת תקלות לפי חודש:**']
        for t in trend[-6:]:
            lines.append(f"• {t['month']}: {t['count']} תקלות")
        return '\n'.join(lines)

    if any(w in msg for w in ['פתוח', 'open', 'ממתין']):
        items = analysis.get('open_items') or []
        if not items:
            return '✓ אין פריטים פתוחים.'
        lines = [f'**{len(items)} פריטים פתוחים:**', '']
        for item in items[:8]:
            desc = item.get('description') or item.get('failure_mode') or item.get('id') or '—'
            lines.append(f"• {desc[:60]}")
        return '\n'.join(lines)

    return (
        f'ניתוחתי {total} תקלות. שאל על:\n'
        '• "ניתוח בעיות שורש"\n'
        '• "תקלות חוזרות"\n'
        '• "סוג הבעיות העיקריות"\n'
        '• "המלצות לביצוע"\n'
        '• "דוח מסכם"'
    )
