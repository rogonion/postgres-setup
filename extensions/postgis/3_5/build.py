import subprocess

from exceptions.exceptions import BuildFailedException

def build_and_get_snippet(postgres_version: str = "17",container_cli_tool: str = "docker")->str:
    """
    Function installs the postgis extension and returns snippet to add to final container.

    Version: 3.5
    """

    container_version = "3.5"
    print(f"-----Setting up postgis extension {container_version} for postgres {postgres_version}-----")
    print("--------------------------------------------------------")

    return f"""
# --- Adding postgis extension (version: {container_version}) ---
RUN dnf -y install https://download.postgresql.org/pub/repos/yum/reporpms/F-42-x86_64/pgdg-fedora-repo-latest.noarch.rpm && \
    dnf -y install postgis35_17 && dnf clean all
"""