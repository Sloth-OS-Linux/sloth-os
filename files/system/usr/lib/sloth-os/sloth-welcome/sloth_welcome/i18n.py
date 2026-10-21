"""Sloth Welcome's translations (translations/<language>.json); the logic is in the shared sloth_common.i18n."""
from pathlib import Path

from sloth_common.i18n import Catalog

catalog = Catalog(Path(__file__).resolve().parent / "translations")

available = catalog.available
system_language = catalog.system_language
set_language = catalog.set_language
language = catalog.language
is_rtl = catalog.is_rtl
strings = catalog.strings
tr = catalog.tr
