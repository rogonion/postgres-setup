from typing import List, Dict, Any
from ..distro_base import BaseDistro

class Suse(BaseDistro):
    def _get_arg_list(self, args: Dict[str, Any], key: str) -> List[str]:
        """Helper to safely extract list arguments"""
        if args and key in args and isinstance(args[key], list):
            return args[key]
        return []

    def refresh_package_repository(self, args: Dict[str, Any] = None):
        # Base flags
        flags = ["--non-interactive"]
        # Safe extension of flags
        flags.extend(self._get_arg_list(args, "flags"))

        self.container.run(
            command=["zypper"] + flags + ["refresh"]
        )

    def install_packages(self, packages: List[str], extra_cache_keys: Dict[str, str] = None, args: Dict[str, Any] = None):
        if not packages:
            return

        flags = ["--non-interactive"]
        flags.extend(self._get_arg_list(args, "flags"))

        install_flags = ["--no-recommends"]
        install_flags.extend(self._get_arg_list(args, "install_flags"))

        cmd = ["zypper"] + flags + ["install"] + install_flags + packages

        if extra_cache_keys:
            self.container.run_cached(
                command=cmd,
                extra_cache_keys=extra_cache_keys
            )
        else:
            self.container.run(command=cmd)

    def remove_packages(self, packages: List[str], args: Dict[str, Any] = None):
        if not packages:
            return

        flags = ["--non-interactive"]
        flags.extend(self._get_arg_list(args, "flags"))

        remove_flags = ["--clean-deps"]
        remove_flags.extend(self._get_arg_list(args, "remove_flags"))

        self.container.run(
            command=["zypper"] + flags + ["remove"] + remove_flags + packages
        )

    def clean_package_repository_cache(self, args: Dict[str, Any] = None):
        flags = ["--non-interactive"]
        flags.extend(self._get_arg_list(args, "flags"))

        clean_flags = ["--all"]
        clean_flags.extend(self._get_arg_list(args, "clean_flags"))

        self.container.run(
            command=["zypper"] + flags + ["clean"] + clean_flags
        )

    def remove_package_manager(self):
        self.container.run(
            command=[
                "sh", "-c",
                """
                rpm -e --nodeps --allmatches zypper rpm libzypp &&
                rm -rf /var/lib/rpm /var/cache/zypp /usr/lib/sysimage/rpm
                """
            ]
        )