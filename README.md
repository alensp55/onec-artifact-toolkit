# 1C external artifact toolkit

CLI for XML source trees of 1C external reports and data processors.

## Commands

- `manifest` — create a reproducible file manifest;
- `compare` — compare two source trees;
- `copy-module` — replace a BSL module without changing target encoding;
- `check` — validate lines and whitespace;
- `release-scan` — search for blocked terms and secret patterns.
- `dump` — export an EPF or ERF to XML source files through Designer;
- `build` — build an EPF or ERF from XML source files through Designer.

## Install

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e .
```

Python 3.11+. Runtime dependencies are not required.

## Example

```powershell
onec-artifact manifest .\source -o .\source.manifest.json
onec-artifact check .\source --max-line-length 120
onec-artifact compare .\source .\roundtrip --fail-on-change
onec-artifact copy-module .\patch\ObjectModule.bsl .\source\Ext\ObjectModule.bsl
onec-artifact release-scan . --denylist .\release-denylist.example.txt
```

## Designer

The toolkit can call an installed Designer without storing credentials. If authentication is required, pass the names
of environment variables. Their values are not included in dry-run output.

```powershell
onec-artifact dump `
  --designer "C:\Tools\1cv8.exe" `
  --file-base .\empty-base `
  .\sample.epf .\source\sample.xml
```

For authenticated runs, use `--user-env` and `--password-env` with variables supplied by the operating system or CI.
Use `--dry-run` to inspect the command with the user and password redacted.

## Test

```powershell
python -m unittest discover -s tests
```

MIT License.
