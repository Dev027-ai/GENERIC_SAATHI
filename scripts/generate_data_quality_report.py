import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services.catalogue import quality_report
import pandas as pd

report = quality_report()
out = ROOT / 'data' / 'reports'
out.mkdir(parents=True, exist_ok=True)
(out / 'data-quality.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
# Export all 130 records for manual review because the supplied file flags all of them.
common = pd.read_csv(ROOT / 'data' / 'input' / 'generic_saathi_common_medicines_130(1).csv')
common.to_csv(out / 'branded_price_review_required.csv', index=False)
jan = pd.read_csv(ROOT / 'data' / 'input' / 'jan_aushadhi_extracted(2).csv')
jan.to_csv(out / 'jan_aushadhi_review_required.csv', index=False)
print(json.dumps(report, indent=2))
