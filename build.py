import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import List

from extensions.add_extensions import add_extensions


def main():
    postgres_version = Path("POSTGRES_VERSION").read_text().strip()

    parser = argparse.ArgumentParser(
        description=f'Build a custom PostgresSQL {postgres_version} container image with extensions. Uses fedora as the base image.')

    parser.add_argument("-c", "--cli-tool", type=str,
                        help="Default: docker | Container engine cli to use | Should support the Docker CLI Format | Example: `podman`")

    parser.add_argument("-n", "--image-name", type=str,
                        help="Default: fedora-postgres | Name of the final postgres container image | Example: `fedora-postgres`")

    parser.add_argument("-t", "--image-tag", type=str,
                        help="Default: latest | Tag for the final postgres container image | Example: `17`")

    parser.add_argument("-e", "--extensions", type=str,
                        help="Comma-separated list of extensions to add | Example: `mysql_fdw:latest,postgis:3.5.3`")

    args = parser.parse_args()

    container_cli_tool = args.cli_tool if isinstance(args.cli_tool, str) else "docker"
    container_image_name = args.image_name if isinstance(args.image_name, str) else "fedora-postgres"
    container_image_tag = args.image_tag if isinstance(args.image_tag, str) else "latest"
    extensions: List[str] = args.extensions.split(",") if isinstance(args.extensions, str) and len(
        args.extensions.strip()) > 0 else []

    print(f"""
---------------------------------------
Building using the following arguments:
- container_cli_tool: {container_cli_tool}
- container_image_name: {container_image_name}
- container_image_tag: {container_image_tag}
- extensions: {extensions}
---------------------------------------
    """)

    base_container_file_path = Path("Containerfile")
    if not base_container_file_path.exists():
        print(f"Error: base container file does not exist: {base_container_file_path}")
        return 1
    base_container_file = base_container_file_path.read_text()

    extension_snippets = ""
    if len(extensions) > 0:
        extension_snippets = add_extensions(postgres_version, container_cli_tool=container_cli_tool,
                                            extensions=extensions)

    # Create the temporary Containerfile in the current directory
    with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=".", suffix=".Containerfile") as temp_containerfile:
        temp_containerfile.write(base_container_file)
        if extension_snippets:
            temp_containerfile.write("\n")
            temp_containerfile.write(extension_snippets)
        temp_containerfile_path = temp_containerfile.name

    try:
        print(f"-----Building final container image {container_image_tag}-----")
        # The build context is the current directory (".")
        subprocess.run(
            [container_cli_tool, "build", "-t", f"{container_image_name}:{container_image_tag}", "-f",
             temp_containerfile_path, "."],
            check=True
        )
        print("--------------------------------------------------------")
        print(f"Build complete: {container_image_name}:{container_image_tag}")
    except subprocess.CalledProcessError as e:
        print(f"Build failed with an error: {e}")
        return 1
    finally:
        # Clean up the temporary Containerfile
        Path(temp_containerfile_path).unlink(missing_ok=True)
        print(f"Removed temporary file: {temp_containerfile_path}")

    return 0


if __name__ == "__main__":
    exit(main())
