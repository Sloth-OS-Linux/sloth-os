"""The .exe handler's translations (translations/<language>.json); the logic is in the shared sloth_common.i18n."""
from pathlib import Path

from sloth_common.i18n import Catalog

catalog = Catalog(Path(__file__).resolve().parent / "translations")
tr = catalog.tr
