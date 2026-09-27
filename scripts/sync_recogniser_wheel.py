"""Put the wheel built for this deployment into the browser page."""

import re
from pathlib import Path


def sync(page: Path, wheel_dir: Path) -> None:
    wheels = list(wheel_dir.glob("quid2pmi-*-py3-none-any.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one quid2pmi wheel in {wheel_dir}, found {len(wheels)}")

    source = page.read_text()
    updated, count = re.subn(
        r'const RECOGNISER = "[^"]+";',
        f'const RECOGNISER = "./{wheels[0].name}";',
        source,
    )
    if count != 1:
        raise RuntimeError(f"expected one RECOGNISER declaration in {page}, found {count}")
    page.write_text(updated)


if __name__ == "__main__":
    sync(Path("web/index.html"), Path("web"))
