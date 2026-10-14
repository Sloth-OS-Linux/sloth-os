"""Az .exe kezelő fordításai (translations/<nyelv>.json); a működés a közös sloth_common.i18n-ben van."""
from pathlib import Path

from sloth_common.i18n import Catalog

catalog = Catalog(Path(__file__).resolve().parent / "translations")
tr = catalog.tr
