import subprocess

from exceptions.exceptions import BuildFailedException

def build_and_get_snippet(postgres_version: str = "17",container_cli_tool: str = "docker")->str:
    """
    Function builds msql_fdw extension and returns snippet to add to final container.

    Version: 2.9.2
    """

    container_name = "postgres-mysql_fdw-extension_build"
    container_version = "2.9.2"
    container_tag = f"{postgres_version}-{container_version}"
    print(f"-----Building mysql fdw extension build container image {container_version} for postgres {postgres_version}-----")
    current_lib_mysqlclient_file = "libmysqlclient.so.24"

    try:
        subprocess.run(
            [container_cli_tool, "build", "-t", f"{container_name}:{container_tag}", "-f", f"extensions/mysql_fdw/{container_version.replace(".","_")}/Containerfile", "."],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise BuildFailedException(container_name=f"{container_name}:{container_version}", cause=e)
    print("--------------------------------------------------------")

    return f"""
# --- Adding mysql_fdw extension (version: {container_tag}) ---
COPY --from={container_name}:{container_tag} /usr/pgsql-17/share/extension/mysql_fdw.control /usr/pgsql-17/share/extension/
COPY --from={container_name}:{container_tag} /usr/pgsql-17/share/extension/mysql_fdw--1.2.sql /usr/pgsql-17/share/extension/
COPY --from={container_name}:{container_tag} /usr/pgsql-17/lib/mysql_fdw.so /usr/pgsql-17/lib/
RUN dnf -y install mysql8.4-libs && dnf clean all

# Find the library path, create the symlink, and set LD_LIBRARY_PATH
RUN MYSQL_LIB_PATH=$(find /usr -name '{current_lib_mysqlclient_file}' -exec dirname {{}} \;) && \
    ln -s "$MYSQL_LIB_PATH/{current_lib_mysqlclient_file}" /usr/lib64/libmysqlclient.so && \
    echo "export LD_LIBRARY_PATH=\"$MYSQL_LIB_PATH:\$LD_LIBRARY_PATH\"" >> /etc/profile.d/mysql_fdw.sh && \
    chmod +x /etc/profile.d/mysql_fdw.sh
"""