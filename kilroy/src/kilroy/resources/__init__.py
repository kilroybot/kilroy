from importlib.resources import path
from pathlib import Path, PurePath
from typing import ContextManager, Tuple, Union


def extract_resource_path(
    resource_path: Union[str, PurePath]
) -> Tuple[str, str]:
    """Returns path to resource as tuple with parent part (as package with dots) and resource name."""
    resource_path = PurePath(resource_path)
    if not resource_path.is_relative_to(PurePath(".")):
        raise ValueError(
            f"Path has to be relative to current dir, but '{resource_path}' is not"
        )
    if ".." in resource_path.parts:
        raise ValueError(
            f"Path can't go backwards, but '{resource_path}' does"
        )
    return ".".join(resource_path.parent.parts), resource_path.name


def resource(resource_path: Union[str, PurePath]) -> ContextManager[Path]:
    """Wrapper to importlib.resources.path with package part filled."""
    package_part, resource_name = extract_resource_path(resource_path)
    package_part = f"{__name__}{'.' + package_part if package_part else ''}"
    return path(package_part, resource_name)


def resource_bytes(resource_path: Union[str, PurePath]) -> bytes:
    """Wrapper to Path.read_bytes() that uses resource(resource_path)."""
    with resource(resource_path) as r:
        return r.read_bytes()


def resource_text(
    resource_path: Union[str, PurePath],
    encoding: str = None,
    errors: str = None,
) -> str:
    """Wrapper to Path.read_text() that uses resource(resource_path)."""
    with resource(resource_path) as r:
        return r.read_text(encoding, errors)
