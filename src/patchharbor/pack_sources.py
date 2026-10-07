"""Internal, bounded capture of explicitly prepared Patch-Package contents.

The shared format-1 path, mode and static script validators retain their error
categories; the public pack engine consumes this immutable capture.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import stat

from patchharbor.bundle_paths import normalize_bundle_path, validate_bundle_member_paths
from patchharbor.errors import FailureReason, PatchHarborError, patch_package_error
from patchharbor.models import BundlePayload
from patchharbor.interpreters import select_interpreter
from patchharbor.patch_package import parse_package_entrypoint
from patchharbor.payload_modes import DEFAULT_PAYLOAD_MODE, validate_payload_mode
from patchharbor.platform.filesystem import FileChangedDuringRead, UnsupportedFileTypeError
from patchharbor.platform.source_tree import SourceDirectory, metadata_signature, open_source_root
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy


MAX_SCAN_NODES=10_000
GENERATED_ENTRIES=3  # patch.json and the two passive handoff files


def resolve_output_target(output: Path, *, contents_root: Path) -> Path:
    """Resolve the chosen output parent; never allow replacement or tree aliases."""
    if not isinstance(output,Path) or not isinstance(contents_root,Path):
        raise TypeError('output and contents_root must be Path objects')
    try:
        parent=output.parent.resolve(strict=True)
        if not parent.is_dir() or parent.is_relative_to(contents_root):
            raise ValueError('output must be outside the content tree in an existing directory')
        target=parent/output.name
        # lstat includes dangling links and hardlink aliases to any input/runtime.
        try:
            target.lstat()
        except FileNotFoundError:
            return target
        raise ValueError('output already exists')
    except (OSError,ValueError,RuntimeError) as exc:
        raise PatchHarborError(f'invalid pack output {output}: {exc}',
                              FailureReason.PAYLOAD_PREPARATION_ERROR) from exc


def _source_error(path: object, exc: object) -> PatchHarborError:
    return PatchHarborError(f'cannot capture pack source {path}: {exc}',FailureReason.SOURCE_ERROR)


@dataclass(frozen=True, slots=True)
class SourceEntry:
    path: str
    directory: bool
    metadata: os.stat_result


@dataclass(frozen=True, slots=True)
class CapturedSources:
    root: Path
    root_signature: tuple[int, ...]
    inventory: tuple[SourceEntry, ...]
    files: tuple[BundlePayload, ...]
    descriptor_states: tuple[tuple[str, os.stat_result], ...]
    entrypoint: str
    empty_directories: int
    warnings: tuple[str, ...]

    def revalidate(self, *, resource_policy: ResourcePolicy=DEFAULT_RESOURCE_POLICY) -> None:
        """Reject known additions, removals, replacements and content metadata changes."""
        try:
            with open_source_root(self.root) as root:
                entries,_=_inventory(root,resource_policy,dict(self.descriptor_states))
                if (metadata_signature(root.metadata)!=self.root_signature
                        or _signature(entries)!=_signature(self.inventory)):
                    raise FileChangedDuringRead('source-inventory-changed')
        except (OSError,ValueError,FileChangedDuringRead,UnsupportedFileTypeError) as exc:
            raise _source_error(self.root,exc) from exc


def _signature(entries: tuple[SourceEntry, ...]) -> tuple:
    return tuple((e.path,e.directory,metadata_signature(e.metadata)) for e in entries)


def _inventory(root: SourceDirectory, policy: ResourcePolicy,
               descriptor_states: Mapping[str, os.stat_result] | None=None
               ) -> tuple[tuple[SourceEntry, ...],int]:
    entries=[]
    nodes=1  # Include the chosen root itself, including an empty root.
    file_count=0
    declared_bytes=0
    empty=0

    def visit(directory: SourceDirectory, prefix: str) -> None:
        nonlocal nodes,file_count,declared_bytes,empty
        children=[]
        with directory.entries() as iterator:
            for child in iterator:
                nodes+=1
                if nodes>MAX_SCAN_NODES:
                    raise ValueError('pack scan node budget exceeded')
                metadata=directory.child_stat(child.name)
                is_directory=stat.S_ISDIR(metadata.st_mode)
                path=prefix+child.name
                normalize_bundle_path(path+'/' if is_directory else path,is_directory=is_directory)
                if ((not is_directory and not stat.S_ISREG(metadata.st_mode))
                        or getattr(metadata,'st_file_attributes',0)&0x400
                        or (not is_directory and metadata.st_nlink>1)):
                    raise UnsupportedFileTypeError('links and special sources are unsupported')
                first=path.split('/',1)[0].casefold()
                if first in ('patch.json','patchharbor_meta'):
                    raise patch_package_error('pack source includes a generated reserved path: '+path)
                entry=SourceEntry(path,is_directory,metadata)
                entries.append(entry);children.append(entry)
                if not is_directory:
                    file_count+=1;declared_bytes+=metadata.st_size
                    if (file_count+GENERATED_ENTRIES>policy.max_zip_entries
                            or metadata.st_size>policy.max_content_bytes
                            or declared_bytes>policy.max_zip_total_bytes):
                        raise ValueError('pack source budget exceeded')
                    if descriptor_states is not None and path in descriptor_states:
                        directory.revalidate_file(child.name,metadata,descriptor_states[path])
        if not children:
            empty+=1
        for entry in sorted(children,key=lambda e:e.path):
            if entry.directory:
                with directory.child(entry.path.rsplit('/',1)[-1],entry.metadata) as child:
                    visit(child,entry.path+'/')

    visit(root,'')
    validate_bundle_member_paths((e.path+'/' if e.directory else e.path,e.directory) for e in entries)
    return tuple(sorted(entries,key=lambda e:e.path)),empty


def resolve_content_root(contents: Path) -> Path:
    try:
        return contents.resolve(strict=True)
    except (OSError, ValueError, RuntimeError) as exc:
        raise _source_error(contents, exc) from exc


def capture_sources(contents: Path, entrypoint: str, *, modes: Mapping[str,int] | None=None,
                    resource_policy: ResourcePolicy=DEFAULT_RESOURCE_POLICY,
                    resolved_root: Path | None=None) -> CapturedSources:
    """Capture all selected files without rewriting any bytes or running scripts."""
    if not isinstance(contents,Path) or not isinstance(entrypoint,str):
        raise TypeError('contents must be Path and entrypoint must be str')
    if not entrypoint:
        raise ValueError('entrypoint must not be empty')
    if modes is not None and not isinstance(modes,Mapping):
        raise TypeError('modes must be a mapping')
    requested=dict(modes or {})
    if any(not isinstance(k,str) or type(v) is not int for k,v in requested.items()):
        raise TypeError('mode keys must be strings and values must be integers, not bool')
    try:
        normalize_bundle_path(entrypoint)
        for name,mode in requested.items():
            normalize_bundle_path(name)
            validate_payload_mode(mode)
        root=resolve_content_root(contents) if resolved_root is None else resolved_root
        with open_source_root(root) as directory:
            inventory,empty=_inventory(directory,resource_policy)
            files={e.path:e for e in inventory if not e.directory}
            if entrypoint not in files:
                raise patch_package_error('entrypoint is absent from pack contents')
            if set(requested)-set(files):
                raise patch_package_error('mode key does not name an input file')
            by_parent={}
            for entry in inventory:
                parent=entry.path.rpartition('/')[0]
                by_parent.setdefault(parent,[]).append(entry)
            payloads=[]
            descriptor_states=[]
            total=0

            def capture(current: SourceDirectory, prefix: str) -> None:
                nonlocal total
                for entry in by_parent.get(prefix,()):
                    name=entry.path.rsplit('/',1)[-1]
                    if entry.directory:
                        with current.child(name,entry.metadata) as child:
                            capture(child,entry.path)
                    else:
                        captured_file=current.read_file(name,entry.metadata,max_bytes=min(
                            resource_policy.max_content_bytes,resource_policy.max_zip_total_bytes-total))
                        content=captured_file.content
                        descriptor_states.append((entry.path,captured_file.descriptor_metadata))
                        total+=len(content)
                        payloads.append(BundlePayload(entry.path,content,requested.get(entry.path,DEFAULT_PAYLOAD_MODE)))
            capture(directory,'')
            ordered=tuple(sorted(payloads,key=lambda p:p.relative_path))
            parsed=parse_package_entrypoint(next(p for p in ordered if p.relative_path==entrypoint))
            select_interpreter(parsed.text)
            warnings=tuple(w for p in ordered if (w:=resource_policy.large_content_warning(p.relative_path,len(p.content))))
            warnings+=parsed.warnings
            if empty:
                warnings+=(f'{empty} empty content directories are not represented in the package',)
            captured=CapturedSources(root,metadata_signature(directory.metadata),inventory,ordered,
                                     tuple(descriptor_states),entrypoint,empty,warnings)
            captured.revalidate(resource_policy=resource_policy)
            return captured
    except (OSError,ValueError,FileChangedDuringRead,UnsupportedFileTypeError) as exc:
        raise _source_error(contents,exc) from exc
