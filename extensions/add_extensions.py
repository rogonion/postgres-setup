from pathlib import Path
from typing import List

from exceptions.exceptions import ExtensionNotValid


def import_from_string(module_name: str, function_name: str):
    try:
        module = __import__(module_name, fromlist=[function_name])
        return getattr(module, function_name)
    except (ImportError, AttributeError) as e:
        print(f"Error: Could not import {function_name} from {module_name}. {e}")
        return None


def add_extensions(postgres_version: str, extensions: List[str] = None, container_cli_tool: str = "docker") -> str:
    """Function builds listed extensions and returns snippet to add to final Containerfile."""
    extension_snippets = ""

    if extensions is None:
        return extension_snippets

    print(f"Processing extensions: {extensions}")
    print()

    for extension in extensions:
        extension_split = extension.split(":")
        extension_name = extension_split[0]
        extension_version = extension_split[1] if len(extension_split) > 1 else "latest"

        extension_directory = Path(f"extensions/{extension_name}")
        if not extension_directory.is_dir():
            raise ExtensionNotValid(extension_name, cause=f"Extension Directory '{extension_directory.name}' not found")

        if extension_version == "latest":
            extension_latest = extension_directory.joinpath("LATEST")
            if not extension_latest.is_file():
                raise ExtensionNotValid(extension_name,
                                        cause=f"Extension Latest file '{extension_latest.name}' not found")
            extension_version = extension_latest.read_text().strip()

        # Dynamically import the build function from the extension module
        add_extension_func = import_from_string(
            f"extensions.{extension_name}.{extension_version.replace(".", "_")}.build",
            "build_and_get_snippet")
        if add_extension_func:
            snippet = add_extension_func(postgres_version=postgres_version, container_cli_tool=container_cli_tool)
            extension_snippets += snippet
        else:
            raise ExtensionNotValid(extension_name,
                                    cause=f"Build function for '{extension_name}:{extension_version}' not found.")

    return extension_snippets
