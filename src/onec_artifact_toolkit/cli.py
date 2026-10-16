from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
import json
import sys

from .checks import check_source_tree, load_denylist, release_scan
from .designer import (
    DesignerCommand,
    Infobase,
    build_dump_command,
    build_load_command,
    execute_designer,
)
from .manifest import (
    TextDocument,
    build_manifest,
    compare_manifests,
    read_text_document,
    save_manifest,
    write_text_document,
)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="onec-artifact")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest", help="Create a deterministic tree manifest")
    manifest_parser.add_argument("root", type=Path)
    manifest_parser.add_argument("-o", "--output", type=Path, required=True)

    compare_parser = subparsers.add_parser("compare", help="Compare two exported source trees")
    compare_parser.add_argument("before", type=Path)
    compare_parser.add_argument("after", type=Path)
    compare_parser.add_argument("--fail-on-change", action="store_true")

    check_parser = subparsers.add_parser("check", help="Run BSL text checks")
    check_parser.add_argument("root", type=Path)
    check_parser.add_argument("--max-line-length", type=int, default=120)

    copy_parser = subparsers.add_parser("copy-module", help="Replace a module and preserve target format")
    copy_parser.add_argument("source", type=Path)
    copy_parser.add_argument("target", type=Path)

    scan_parser = subparsers.add_parser("release-scan", help="Search a tree for forbidden terms and secrets")
    scan_parser.add_argument("root", type=Path)
    scan_parser.add_argument("--denylist", type=Path)

    dump_parser = subparsers.add_parser("dump", help="Export an EPF or ERF to XML source files")
    add_designer_arguments(dump_parser)
    dump_parser.add_argument("artifact", type=Path)
    dump_parser.add_argument("root_xml", type=Path)

    build_parser = subparsers.add_parser("build", help="Build an EPF or ERF from XML source files")
    add_designer_arguments(build_parser)
    build_parser.add_argument("root_xml", type=Path)
    build_parser.add_argument("artifact", type=Path)
    return parser


def add_designer_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--designer", type=Path, required=True)
    base = parser.add_mutually_exclusive_group(required=True)
    base.add_argument("--file-base", type=Path)
    base.add_argument("--server-base")
    parser.add_argument("--user-env")
    parser.add_argument("--password-env")
    parser.add_argument("--log", type=Path, default=Path("onec-artifact.log"))
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true")


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def command_manifest(args: Namespace) -> int:
    manifest = build_manifest(args.root)
    save_manifest(manifest, args.output)
    print(f"Saved {len(manifest['files'])} records to {args.output}")
    return 0


def command_compare(args: Namespace) -> int:
    result = compare_manifests(build_manifest(args.before), build_manifest(args.after))
    print_json(result)
    changed = any(result.values())
    return 1 if changed and args.fail_on_change else 0


def command_check(args: Namespace) -> int:
    findings = check_source_tree(args.root, args.max_line_length)
    print_json([finding.to_dict() for finding in findings])
    return 1 if findings else 0


def command_copy_module(args: Namespace) -> int:
    source = read_text_document(args.source)
    if source is None:
        raise ValueError(f"Source is not a supported text file: {args.source}")
    target = read_text_document(args.target)
    if target is None:
        target = TextDocument("", source.encoding, source.newline)
    write_text_document(args.target, target, source.text)
    print(f"Updated {args.target} using {target.encoding}/{target.newline}")
    return 0


def command_release_scan(args: Namespace) -> int:
    excluded_paths = [args.denylist] if args.denylist is not None else []
    findings = release_scan(args.root, load_denylist(args.denylist), excluded_paths)
    print_json([finding.to_dict() for finding in findings])
    return 1 if findings else 0


def command_dump(args: Namespace) -> int:
    infobase = infobase_from_arguments(args)
    command = build_dump_command(args.designer, infobase, args.artifact, args.root_xml, args.log)
    return run_designer_command(command, args)


def command_build(args: Namespace) -> int:
    infobase = infobase_from_arguments(args)
    command = build_load_command(args.designer, infobase, args.artifact, args.root_xml, args.log)
    return run_designer_command(command, args)


def infobase_from_arguments(args: Namespace) -> Infobase:
    if args.file_base is not None:
        infobase = Infobase.file(args.file_base)
    else:
        infobase = Infobase.server(args.server_base)
    return infobase.with_environment_credentials(args.user_env, args.password_env)


def run_designer_command(command: DesignerCommand, args: Namespace) -> int:
    if args.dry_run:
        print_json({"command": command.display_arguments()})
        return 0
    result = execute_designer(command, args.timeout)
    print_json({"exitCode": result.return_code, "log": str(result.log_path)})
    return 0 if result.succeeded else 1


def main() -> None:
    args = create_parser().parse_args()
    handlers = {
        "manifest": command_manifest,
        "compare": command_compare,
        "check": command_check,
        "copy-module": command_copy_module,
        "release-scan": command_release_scan,
        "dump": command_dump,
        "build": command_build,
    }
    try:
        exit_code = handlers[args.command](args)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        exit_code = 2
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
