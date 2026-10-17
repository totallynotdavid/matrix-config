import json
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from string import Template
from typing import Any

from .support import CHART, NAMESPACE, RELEASE, VALUES_TEMPLATE, Failure, run


@contextmanager
def rendered_values(deployment: Any, organization: Any) -> Iterator[Path]:
    values = {
        "brand_json": json.dumps(deployment["brand"], ensure_ascii=False),
        "administrator_username": organization["administrator"]["username"],
        "chat_url": deployment["urls"]["chat"],
        **{f"{name}_host": host for name, host in deployment["hosts"].items()},
    }
    try:
        rendered = Template(VALUES_TEMPLATE.read_text()).substitute(values)
    except (KeyError, ValueError) as error:
        raise Failure(f"Invalid chart values template: {error}") from error
    with tempfile.NamedTemporaryFile(
        mode="w", prefix="element-values-", suffix=".yaml", delete=False
    ) as temporary:
        temporary.write(rendered)
        path = Path(temporary.name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def validate(deployment: Any, organization: Any) -> str:
    run(["helm", "dependency", "build", CHART])
    with rendered_values(deployment, organization) as values:
        run(["helm", "lint", CHART, "--values", values, "--strict"])
        return run(
            [
                "helm",
                "template",
                RELEASE,
                CHART,
                "--namespace",
                NAMESPACE,
                "--values",
                values,
            ],
            capture=True,
        )
