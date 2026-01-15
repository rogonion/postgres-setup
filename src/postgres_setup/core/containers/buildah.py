import hashlib
import json
import sys
from pathlib import Path
from typing import Any, List, Optional, Dict, Tuple

import sh
from rich.console import Console

from ..spec import BuildSpec

console = Console()


def prune_cache_images(buildah_path: str, cache_prefix: str):
    if len(cache_prefix) == 0:
        raise RuntimeError("cache_prefix is empty")
    try:
        buildah_cmd = sh.Command(buildah_path)
    except sh.CommandNotFound:
        raise RuntimeError(f"Buildah executable not found at {buildah_path}")

    try:
        output = buildah_cmd("images", "--json")
    except sh.ErrorReturnCode:
        console.print("[red]Failed to list images.[/red]")
        return

    try:
        images_list = json.loads(output)
    except json.JSONDecodeError:
        console.print("[red]Failed to parse Buildah output.[/red]")
        return

    targets = []

    if images_list:
        for img_data in images_list:
            # The 'names' field is a list of strings like "localhost/my-image:tag"
            # Some images (dangling) might not have names, so we check existence
            names = img_data.get("names", [])
            if not names:
                continue

            for name in names:
                # Buildah sometimes adds 'localhost/' prefix automatically
                # We check if the name contains our cache prefix
                if cache_prefix in name:
                    targets.append(name)

    if not targets:
        console.print(f"[yellow]No cache layers found for prefix '{cache_prefix}'[/yellow]")
        return

    console.print(f"[bold red]Found {len(targets)} cache layers to remove...[/bold red]")

    for img in targets:
        try:
            console.print(f" -> Deleting {img}")
            buildah_cmd("rmi", img)
        except sh.ErrorReturnCode as e:
            console.print(f"[dim]Failed to remove {img} (might be in use or dependent): {e}[/dim]")

    for tag in targets:
        try:
            console.print(f" -> Deleting {tag}")
            buildah_cmd("rmi", tag)
        except sh.ErrorReturnCode as e:
            # Often images are deleted in a cascade; ignore 'image not known' errors
            if "image not known" not in str(e):
                console.print(f"[dim]Warning: {e}[/dim]")


class BuildahContainer:
    def __init__(self, base_image: str, image_name: str, config: BuildSpec, cache_prefix: str):
        self.base_image = base_image
        self.current_image = base_image  # Image currently being worked on
        self.image_name = image_name
        self.config = config
        self.cache_prefix = cache_prefix

        try:
            self._buildah_cmd = sh.Command(config.Buildah.Path)
        except sh.CommandNotFound:
            raise RuntimeError(f"Buildah executable not found at {config.Buildah.Path}")

    def __enter__(self):
        self._create_container(self.current_image)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()

    def _create_container(self, from_image: str):
        """
        Create/re-create container image.
        :param from_image:
        :return:
        """
        console.print(f"[dim]Spawning container image from {from_image}[/dim]")

        try:
            self._buildah_cmd("from", "--name", self.image_name, from_image)
        except sh.ErrorReturnCode as e:
            if "already in use" in str(e.stderr):
                self._cleanup()
                self._buildah_cmd("from", "--name", self.image_name, from_image)
            else:
                raise

    def _cleanup(self):
        """
        Remove image_name
        :return:
        """
        try:
            self._buildah_cmd("rm", self.image_name)
        except Exception:
            pass

    def _check_image_exists(self, tag: str) -> bool:
        """
        Return True if image with tag exists.
        :param tag:
        :return:
        """
        try:
            output = self._buildah_cmd("images", "-q", tag)  # returns ID if found else empty.
            return bool(output.strip())
        except sh.ErrorReturnCode:
            return False

    def _calculate_hash(self, inputs: List[Any]) -> str:
        """
        Generate SHA256 hash from inputs (commands, environment variables/arguments, additional command context information like versions)
        :param inputs:
        :return:
        """
        hasher = hashlib.sha256()

        hasher.update(self.current_image.encode('utf-8'))  # Add current image for chain integrity

        for inpt in inputs:
            if isinstance(inpt, dict):
                # Sort keys to ensure {'a':1, 'b':2} always hashes the same as {'b':2, 'a':1}
                s = json.dumps(inpt, sort_keys=True)
            else:
                s = str(inpt)
            hasher.update(s.encode('utf-8'))

        return hasher.hexdigest()[:12]

    def run_cached(self, command: List[str], env: Optional[Dict[str, str]] = None,
                   extra_cache_keys: Optional[Dict[str, str]] = None):
        """
        Executes command and caches the layer.
        Will first check if the layer cache exists.
        :param command:
        :param env:
        :param extra_cache_keys:
        :return:
        """

        hash_inputs = [command, env, extra_cache_keys]
        layer_hash = self._calculate_hash(hash_inputs)
        cache_tag = self.cache_prefix + ":" + layer_hash

        if self._check_image_exists(cache_tag):
            console.print(f"[bold green] Using cached layer {layer_hash}[/bold green]")

            self._cleanup()
            self._create_container(cache_tag)

            self.current_image = cache_tag
            return

        self.run(command, env)

        self.commit(cache_tag)

        self.current_image = cache_tag

    def run(self, command: List[str], env: Optional[Dict[str, str]] = None):
        """
        Executes command with no caching.
        :param command: buildah command
        :param env: environment variables for the command
        :return:
        """
        env_args = []
        if env:
            for k, v in env.items():
                env_args.extend(["-e", f"{k}={v}"])

        console.print(f"[dim]buildah run {' '.join(env_args)} {self.image_name} -- {' '.join(command)}[/dim]")
        self._buildah_cmd("run", *env_args, self.image_name, "--", *command, _out=sys.stdout, _err=sys.stderr)

    def configure(self, configs: List[Tuple[str, str]]):
        args = ["config"]

        for config in configs:
            args.extend([config[0], config[1]])

        args.append(self.image_name)

        console.print(f"[dim]buildah {' '.join(args)}[/dim]")
        self._buildah_cmd(*args)

    def commit(self, tag: str, cmd: Optional[List[str]] = None, changes: Optional[List[str]] = None,
               squash: bool = False):
        args = ["commit"]

        if squash:
            args.append("--squash")

        if cmd:
            args.extend(["--cmd", json.dumps(cmd)])

        if changes:
            for instruction in changes:
                args.extend(["--change", instruction])

        args.extend([self.image_name, tag])

        console.print(f"[dim]buildah {' '.join(args)}[/dim]")
        self._buildah_cmd(*args)

    def run_get_output(self, command: List[str]) -> str:
        """
        Runs command and returns stdout as a string.
        """
        result = self._buildah_cmd("run", self.image_name, "--", *command)

        # Case A: _buildah_cmd returned the output string directly
        if isinstance(result, str):
            return result.strip()

        # Case B: _buildah_cmd returned a sh.RunningCommand object
        # We access .stdout (bytes) and decode it
        if hasattr(result, "stdout"):
            return result.stdout.decode('utf-8').strip()

        # Fallback: Try converting whatever it is to a string
        return str(result).strip()

    def copy_host_container(self, src: Path, dest: str):
        """
        Copies a file or directory from the host into the container.
        """
        if not src.exists():
            raise FileNotFoundError(f"Source file {src} does not exist.")

        console.print(f"[dim]buildah copy {self.image_name} {str(src)} {dest}[/dim]")
        self._buildah_cmd("copy", self.image_name, str(src), dest)

    def copy_container_current(self, src_container: str, src: str, dest: str):
        """
        Copies a files from container to current container
        :param src_container:
        :param src:
        :param dest:
        :return:
        """
        console.print(f"[dim]buildah copy --from {src_container} {self.image_name} {src} {dest}[/dim]")
        self._buildah_cmd("copy", "--from", src_container, self.image_name, src, dest)
