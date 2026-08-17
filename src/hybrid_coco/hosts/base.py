"""base classes and shared install steps for agent hosts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .common import (
    MCP_TOOLS,
    copy_skills,
    merge_mcp_json,
    mcp_registered_json,
    remove_mcp_json,
    skills_src,
)
from .instructions import apply_project_instructions
from .types import HostResult

SkillTarget = tuple[Path, Path | str]


def mcp_registration_lines(label: str) -> list[str]:
    lines = [f"MCP server registered in {label}"]
    lines.extend(MCP_TOOLS)
    return lines


def install_skills_to_targets(targets: list[SkillTarget], host: str) -> tuple[list[str], list[str]]:
    src = skills_src(host)
    skills: list[str] = []
    lines: list[str] = []
    for dst, label in targets:
        skills = copy_skills(dst, src)
        lines.append(f"skills installed in {label}: {', '.join(skills)}")
    return skills, lines


class HostInstaller(ABC):
    name: str
    title: str
    events: tuple[str, ...]

    @abstractmethod
    def install(self, root: Path, *, global_config: bool, home: Path) -> HostResult: ...

    @abstractmethod
    def mcp_registered(self, root: Path, *, home: Path) -> bool: ...

    @abstractmethod
    def hooks_present(self, root: Path, *, home: Path) -> bool: ...

    @abstractmethod
    def mcp_locations(self, root: Path, *, home: Path) -> list[Path]: ...

    @abstractmethod
    def remove_mcp(self, root: Path, *, home: Path) -> list[str]: ...

    def _apply_project(self, root: Path) -> list[str]:
        return apply_project_instructions(root=root, host=self.name)


class JsonMcpHostInstaller(HostInstaller):
    project_mcp_rel: Path
    global_mcp_rel: Path
    project_mcp_label: str
    mcp_servers_key: str = "mcpServers"

    def mcp_path(self, root: Path, *, global_config: bool, home: Path) -> Path:
        if global_config:
            return home / self.global_mcp_rel
        return root / self.project_mcp_rel

    def mcp_label(self, root: Path, *, global_config: bool, home: Path) -> str:
        if global_config:
            return str(self.mcp_path(root, global_config=global_config, home=home))
        return self.project_mcp_label

    def register_mcp(self, root: Path, *, global_config: bool, home: Path) -> list[str]:
        path = self.mcp_path(root, global_config=global_config, home=home)
        merge_mcp_json(path, servers_key=self.mcp_servers_key)
        return mcp_registration_lines(self.mcp_label(root, global_config=global_config, home=home))

    def mcp_registered(self, root: Path, *, home: Path) -> bool:
        project = root / self.project_mcp_rel
        global_cfg = home / self.global_mcp_rel
        return mcp_registered_json(project, servers_key=self.mcp_servers_key) or mcp_registered_json(
            global_cfg, servers_key=self.mcp_servers_key
        )

    def mcp_locations(self, root: Path, *, home: Path) -> list[Path]:
        return [root / self.project_mcp_rel, home / self.global_mcp_rel]

    def remove_mcp(self, root: Path, *, home: Path) -> list[str]:
        path = root / self.project_mcp_rel
        msg = remove_mcp_json(path, servers_key=self.mcp_servers_key)
        if msg is None:
            return [f"no hybrid-coco MCP entry in {path}"]
        return [msg]

    def install_skills(
        self,
        root: Path,
        *,
        global_config: bool,
        home: Path,
        home_skills: Path,
        project_skills: Path | None,
        project_label: Path | str,
    ) -> tuple[list[str], list[str]]:
        targets: list[SkillTarget] = [(home_skills, home_skills)]
        if not global_config and project_skills is not None:
            targets.append((project_skills, project_label))
        return install_skills_to_targets(targets, self.name)
