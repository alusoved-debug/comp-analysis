import os
import pandas as pd
from datetime import datetime

FAILURE_MODE_KEYS = [
    'failure mode', 'fault mode', 'mode', 'failure type',
    'סוג תקלה', 'מצב כשל', 'קוד הפגם', 'סיבת פגם', 'סוג הודעה',
]
ROOT_CAUSE_KEYS = [
    'root cause', 'cause', 'root_cause',
    'סיבת שורש', 'גורם', 'סיבה', 'סיבת פגם', 'אשמת ספק',
]
STATUS_KEYS = [
    'status', 'state', 'open/close',
    'סטטוס', 'מצב', 'סטטוס ההודעה', 'סטטוס תגובת ספק',
]
SEVERITY_KEYS = [
    'severity', 'priority', 'criticality', 'risk',
    'חומרה', 'עדיפות', 'סוג הודעה',
]
DATE_KEYS = [
    'date', 'reported', 'occurred', 'report date', 'failure date',
    'תאריך', 'תאריך פתיחה',
]
SYSTEM_KEYS = [
    'system', 'component', 'part', 'part number', 'assembly', 'project',
    'מערכת', 'רכיב', 'חלק', 'פרויקט', 'תיאור חומר', 'מחלקה',
]
CA_KEYS = [
    'corrective action', 'corrective', 'action', 'ca', 'fix',
    'פעולה מתקנת', 'פעולה מתקנת מיידית',
]
DESCRIPTION_KEYS = [
    'description', 'failure description', 'fault description', 'problem',
    'תיאור', 'תקלה', 'כשל', 'תיאור הודעה', 'טקסט פגם', 'טקסט פעילות ארוך',
]
ID_KEYS = [
    'id', 'number', 'fr number', 'report id', 'fr#',
    'מספר', 'מזהה', 'מספר הודעה',
]
OWNER_KEYS = [
    'owner', 'responsible', 'assigned', 'engineer',
    'אחראי', 'שם יוזם', 'מתאם הודעות איכות', 'שם יושב ראש',
]
STAGE_KEYS = ['שלב גילוי פגם', 'discovery stage', 'stage']


class FaultAnalyzer:
    def __init__(self, filepath):
        self.filepath = filepath
        self.df = None
        self.col_map = {}
        self._load()

    def _load(self):
        ext = os.path.splitext(self.filepath)[1].lower()
        try:
            engine = 'xlrd' if ext == '.xls' else 'openpyxl'
            self.df = pd.read_excel(self.filepath, engine=engine)
        except ImportError:
            self.df = self._load_via_openpyxl()
        self.df.columns = [str(c).strip() for c in self.df.columns]
        self.df = self.df.dropna(how='all').reset_index(drop=True)
        self.col_map = self._detect_columns()

        for col in self.df.columns:
            if 'date' in col.lower() or 'תאריך' in col:
                self.df[col] = pd.to_datetime(self.df[col], errors='coerce')

    def _load_via_openpyxl(self):
        import openpyxl
        wb = openpyxl.load_workbook(self.filepath, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if not rows:
            return pd.DataFrame()
        headers = [str(c).strip() if c is not None else '' for c in rows[0]]
        data = [list(r) for r in rows[1:] if any(v is not None for v in r)]
        return pd.DataFrame(data, columns=headers)

    def _match(self, keys):
        for col in self.df.columns:
            cl = col.lower()
            if any(k in cl or k in col for k in keys):
                return col
        return None

    def _detect_columns(self):
        return {
            'failure_mode': self._match(FAILURE_MODE_KEYS),
            'root_cause': self._match(ROOT_CAUSE_KEYS),
            'status': self._match(STATUS_KEYS),
            'severity': self._match(SEVERITY_KEYS),
            'date': self._match(DATE_KEYS),
            'system': self._match(SYSTEM_KEYS),
            'corrective_action': self._match(CA_KEYS),
            'description': self._match(DESCRIPTION_KEYS),
            'id': self._match(ID_KEYS),
            'owner': self._match(OWNER_KEYS),
            'stage': self._match(STAGE_KEYS),
        }

    def analyze(self):
        out = {
            'total_failures': len(self.df),
            'columns': list(self.df.columns),
            'column_mapping': {k: v for k, v in self.col_map.items() if v},
        }

        if self.col_map['failure_mode']:
            out['failure_mode_distribution'] = self._pareto(self.col_map['failure_mode'])

        if self.col_map['root_cause']:
            out['root_cause_distribution'] = self._pareto(self.col_map['root_cause'])

        if self.col_map['severity']:
            out['severity_distribution'] = self._pareto(self.col_map['severity'])

        if self.col_map['system']:
            out['system_distribution'] = self._pareto(self.col_map['system'])

        if self.col_map['status']:
            out['status_distribution'] = self._pareto(self.col_map['status'])

        if self.col_map['stage']:
            out['stage_distribution'] = self._pareto(self.col_map['stage'])

        if self.col_map['date']:
            out['trend_data'] = self._trend(self.col_map['date'])

        out['metrics'] = self._metrics()
        out['open_items'] = self._open_items()
        out['recurring_faults'] = self._recurring(self.col_map.get('failure_mode'))
        out['recurring_causes'] = self._recurring(self.col_map.get('root_cause'))
        out['recommendations'] = self._recommendations(out)
        out['executive_summary'] = self._executive_summary(out)
        out['summary'] = self._summary(out)
        return out

    def _pareto(self, col):
        counts = self.df[col].astype(str).str.strip().value_counts()
        counts = counts[counts.index.str.lower() != 'nan']
        total = counts.sum()
        if total == 0:
            return []

        cumulative = 0
        result = []
        for name, count in counts.items():
            cumulative += count
            result.append({
                'name': name,
                'count': int(count),
                'percentage': round(float(count) / total * 100, 1),
                'cumulative': round(float(cumulative) / total * 100, 1),
            })
        return result

    def _trend(self, col):
        try:
            df2 = self.df.dropna(subset=[col]).copy()
            if df2.empty:
                return []
            df2[col] = pd.to_datetime(df2[col], errors='coerce')
            df2 = df2.dropna(subset=[col])
            if df2.empty:
                return []
            df2['_month'] = df2[col].dt.to_period('M')
            monthly = df2.groupby('_month').size().reset_index(name='count')
            return [
                {'month': str(r['_month']), 'count': int(r['count'])}
                for _, r in monthly.iterrows()
            ]
        except Exception:
            return []

    def _open_items(self):
        if not self.col_map['status']:
            return []

        closed_words = {
            'closed', 'complete', 'completed', 'done', 'close',
            'סגור', 'הושלם', 'סגורה', 'הודעה סגורה',
        }
        mask = ~self.df[self.col_map['status']].astype(str).str.strip().str.lower().isin(closed_words)
        open_df = self.df[mask].copy()
        rows = []
        for _, r in open_df.head(30).iterrows():
            row = {}
            for key, col in self.col_map.items():
                if col:
                    val = r[col]
                    row[key] = str(val) if pd.notna(val) else ''
            rows.append(row)
        return rows

    def _recurring(self, col):
        if not col:
            return []
        counts = self.df[col].astype(str).str.strip().value_counts()
        counts = counts[counts.index.str.lower() != 'nan']
        total = counts.sum()
        recurring = []
        for name, count in counts.items():
            if count > 1:
                recurring.append({
                    'name': name,
                    'count': int(count),
                    'percentage': round(float(count) / total * 100, 1),
                })
        return sorted(recurring, key=lambda x: x['count'], reverse=True)

    def _recommendations(self, out):
        m = out.get('metrics', {})
        recs = []
        priority = 1

        if m.get('open_items', 0) > 0:
            recs.append({
                'priority': priority,
                'title': 'סגירת פריטים פתוחים',
                'detail': f"יש {m['open_items']} תקלות פתוחות — יש לסגור בהקדם ולעדכן סטטוס",
                'category': 'סגירה',
            })
            priority += 1

        for item in out.get('recurring_faults', [])[:3]:
            recs.append({
                'priority': priority,
                'title': f"טיפול בתקלה חוזרת: {item['name']}",
                'detail': f"מופיעה {item['count']} פעמים ({item['percentage']}%) — נדרש RCA ופעולה מתקנת",
                'category': 'תקלות חוזרות',
            })
            priority += 1

        modes = out.get('failure_mode_distribution') or []
        if modes:
            top = modes[0]
            recs.append({
                'priority': priority,
                'title': f"מיקוד בבעיה עיקרית: {top['name']}",
                'detail': f"{top['percentage']}% מהתקלות — עדיפות לטיפול מערכתי",
                'category': 'בעיות עיקריות',
            })
            priority += 1

        causes = out.get('root_cause_distribution') or []
        if causes:
            top_c = causes[0]
            recs.append({
                'priority': priority,
                'title': f"טיפול בסיבת שורש: {top_c['name']}",
                'detail': f"גורם מוביל ב-{top_c['percentage']}% מהמקרים — בדיקת תהליך/ספק",
                'category': 'RCA',
            })
            priority += 1

        if m.get('closure_rate', 100) < 80:
            recs.append({
                'priority': priority,
                'title': 'שיפור אחוז סגירה',
                'detail': f"אחוז סגירה {m.get('closure_rate')}% — יעד AS9100: 80%+",
                'category': 'איכות',
            })
            priority += 1

        if m.get('ca_coverage', 100) < 95:
            recs.append({
                'priority': priority,
                'title': 'השלמת פעולות מתקנות',
                'detail': f"כיסוי CA {m.get('ca_coverage', 0)}% — יש להשלים תיעוד פעולות מתקנות",
                'category': 'CA',
            })

        if not recs:
            recs.append({
                'priority': 1,
                'title': 'המשך מעקב',
                'detail': 'הנתונים יציבים — המשך מעקב חודשי וניתוח מגמות',
                'category': 'שוטף',
            })

        return recs

    def _executive_summary(self, out):
        m = out.get('metrics', {})
        total = out.get('total_failures', 0)
        top_modes = out.get('failure_mode_distribution') or []
        top_causes = out.get('root_cause_distribution') or []
        recurring = out.get('recurring_faults') or []

        lines = [
            f'נותחו {total} תקלות.',
        ]
        if m.get('closure_rate') is not None:
            lines.append(
                f"אחוז סגירה: {m['closure_rate']}% "
                f"({m.get('closed_items', 0)} סגורות, {m.get('open_items', 0)} פתוחות)."
            )
        if top_modes:
            lines.append(
                f"בעיה עיקרית: {top_modes[0]['name']} ({top_modes[0]['percentage']}% מהמקרים)."
            )
        if top_causes:
            lines.append(
                f"סיבת שורש מובילה: {top_causes[0]['name']} ({top_causes[0]['percentage']}%)."
            )
        if recurring:
            lines.append(f"זוהו {len(recurring)} סוגי תקלה חוזרים.")
        if m.get('ca_coverage') is not None:
            lines.append(f"כיסוי פעולות מתקנות: {m['ca_coverage']}%.")

        return {
            'text': ' '.join(lines),
            'highlights': lines,
        }

    def _metrics(self):
        m = {}
        total = len(self.df)
        if total == 0:
            return m

        if self.col_map['status']:
            closed_words = {
                'closed', 'complete', 'completed', 'done', 'close',
                'סגור', 'הושלם', 'סגורה', 'הודעה סגורה',
            }
            closed = self.df[self.col_map['status']].astype(str).str.strip().str.lower().isin(closed_words).sum()
            m['closure_rate'] = round(float(closed) / total * 100, 1)
            m['open_items'] = int(total - closed)
            m['closed_items'] = int(closed)

        if self.col_map['corrective_action']:
            has_ca = self.df[self.col_map['corrective_action']].notna()
            has_ca &= self.df[self.col_map['corrective_action']].astype(str).str.strip() != ''
            m['ca_coverage'] = round(float(has_ca.sum()) / total * 100, 1)

        if self.col_map['failure_mode']:
            modes = self.df[self.col_map['failure_mode']].astype(str).str.strip().value_counts()
            m['recurring_modes'] = int((modes > 1).sum())
            m['unique_modes'] = int(len(modes))

        if self.col_map['root_cause']:
            roots = self.df[self.col_map['root_cause']].astype(str).str.strip().value_counts()
            m['unique_root_causes'] = int(len(roots))

        return m

    def _summary(self, out):
        s = {
            'total_failures': out['total_failures'],
            'generated_at': datetime.now().isoformat(),
        }
        if 'failure_mode_distribution' in out:
            s['top_3_modes'] = [
                f"{x['name']} ({x['percentage']}%)"
                for x in out['failure_mode_distribution'][:3]
            ]
        if 'root_cause_distribution' in out:
            s['top_3_causes'] = [
                f"{x['name']} ({x['percentage']}%)"
                for x in out['root_cause_distribution'][:3]
            ]
        s['metrics'] = out.get('metrics', {})
        return s
