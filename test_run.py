"""Quick integration test – run with: py test_run.py"""
import json, io, sys
import app as a

with a.app.test_client() as c:
    # 1. Upload sample BOM
    bom_csv = c.get('/sample_bom').data
    r = c.post('/upload',
               data={'bom_file': (io.BytesIO(bom_csv), 'sample_bom.csv')},
               content_type='multipart/form-data')
    up = json.loads(r.data)
    if 'error' in up:
        print('UPLOAD ERROR:', up['error']); sys.exit(1)
    print(f"Upload OK – {up['rows']} rows, columns: {up['columns']}")

    # 2. Run analysis (web_lookup=False for speed)
    r2 = c.post('/analyse', json={
        't_ambient': 40, 'env_code': 'GF', 'quality': 'C',
        'stress_ratio': 0.5, 'web_lookup': False
    })
    res = json.loads(r2.data)
    if 'error' in res:
        print('ANALYSE ERROR:', res['error']); sys.exit(1)

    print(f"\n{'='*50}")
    print(f"  Lambda = {res['total_lambda']:.4f}  failures/10^6 hr")
    print(f"  FIT    = {res['fit_rate']:.2f}  failures/10^9 hr")
    print(f"  MTBF   = {res['mtbf_hours']:,.0f} hr  ({res['mtbf_years']:.1f} years)")
    print(f"{'='*50}")
    print(f"\nPer-component breakdown:")
    print(f"{'RefDes':<8} {'Type':<12} {'Qty':>4} {'lam_unit':>10} {'lam_total':>10}  Source")
    print('-'*60)
    for r_ in res['results']:
        print(f"{r_['ref_des']:<8} {r_['comp_type']:<12} {r_['quantity']:>4} "
              f"{r_['lambda_p']:>10.5f} {r_['lambda_total']:>10.5f}  {r_['data_source']}")

    # 3. Generate Word report
    r3 = c.post('/report', json={
        'project_name': 'בדיקת אינטגרציה',
        'doc_number': 'REL-TEST-001',
        'prepared_by': 'Engineer',
        'revision': 'A'
    })
    print(f"\nReport: status={r3.status_code}, size={len(r3.data):,} bytes")
    if r3.status_code == 200:
        with open('output_report.docx', 'wb') as f:
            f.write(r3.data)
        print("Saved: output_report.docx")

print("\nAll tests passed.")
