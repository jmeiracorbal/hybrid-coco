# Language plugin architecture for hybrid-coco

Status: proposed  
Last updated: 2026-08-18

## Goal

Define a modular architecture to add support for new programming languages in `hybrid-coco` through installable plugins, using a canonical namespace format:

- `author/hc-{code}`

Examples:

- `acme/hc-ruby`
- `jmeiracorbal/hc-zig`

The design must preserve the current product constraints:

- `pip install hybrid-coco && hc init` must keep working with no extra setup
- SQLite only
- FTS5 + tree-sitter before any embedding layer
- MCP tool names `hc_*` remain stable
- no always-on daemon or server-side plugin registry

---

## Current state

Language support is currently static and in-core.

### Source of truth

The current registry lives in:

- `src/hybrid_coco/languages/registry.py`

Its central contract is:

```python
@dataclass(frozen=True)
class LanguageSpec:
    name: str
    extensions: tuple[str, ...]
    load_ts: LanguageLoader
    parser_factory: ParserFactory
    structure_queries: dict[str, str] = field(default_factory=dict)
```

Each language is compiled into the package through:

1. a `tree-sitter-*` dependency in `pyproject.toml`
2. a parser implementation under `src/hybrid_coco/parsers/`
3. one `LanguageSpec` entry in `LANGUAGE_SPECS`
4. tests in `tests/test_languages.py` and `tests/test_registry.py`
5. README updates

### Current runtime flow

1. `indexer.py` walks files
2. `parsers.resolve_language()` resolves extension overrides first, then built-in extension map
3. `create_parser(language)` comes from `languages/registry.py`
4. the parser extracts `Symbol` values
5. results are stored in SQLite

### Important limitations today

- no dynamic discovery of language extensions
- no entry points
- no install/uninstall lifecycle for language modules
- `settings.py` rejects languages outside `KNOWN_LANGUAGES`
- `plugin/` is the Claude Code plugin, not a language extension system

---

## Design principles

### 1. core remains self-contained

The base package must continue shipping the current built-in language set. Plugins are opt-in and cannot become mandatory for a normal install.

### 2. plugins extend the same runtime contracts

A plugin must not invent a different parser abstraction. It must implement the same public contracts already used by the core:

- `LanguageSpec`
- `Parser`
- `Symbol`

### 3. plugin discovery is local and deterministic

Discovery must happen in-process using Python package metadata, without network calls, background services, or remote registries.

### 4. replacement is explicit and stable

If multiple plugins target the same language, the most recently installed plugin becomes the active implementation for that language.

### 5. uninstall is first-class

Removing a plugin must restore the next valid implementation automatically, either:

- the previous plugin for that language
- or the core implementation when one exists

### 6. contract validation fails explicitly

If a plugin does not satisfy the contract, `hybrid-coco` should fail the plugin activation explicitly. It should not silently guess defaults or proceed with partial fallback behavior.

---

## Proposed identity model

The plugin identity has three different concepts and they should not be conflated.

| Concept | Example | Purpose |
|--------|---------|---------|
| canonical plugin id | `acme/hc-ruby` | user-facing unique id |
| language code | `ruby` | runtime conflict domain |
| python distribution name | `hc-ruby` | pip installation target |

### Canonical plugin id

The canonical id uses the required namespace format:

- `author/hc-{code}`

This is the identifier to persist in plugin metadata and config files.

### Distribution name

The Python package published to PyPI cannot literally use `/`, so the installable distribution remains a normal package name, for example:

- `hc-ruby`
- `acme-hc-ruby`

The distribution must expose the canonical plugin id through the plugin manifest returned at runtime.

---

## Proposed plugin contract

Introduce a new public module:

- `src/hybrid_coco/languages/contract.py`

It should define a manifest structure for external language plugins.

### Manifest

```python
@dataclass(frozen=True)
class LanguagePluginManifest:
    plugin_id: str
    version: str
    min_hc_version: str
    languages: tuple[LanguageSpec, ...]
    distribution: str
```

### Entry point group

Use Python entry points:

```toml
[project.entry-points."hybrid_coco.languages"]
"acme/hc-ruby" = "hc_ruby:register"
```

The entry point must return one manifest:

```python
def register() -> LanguagePluginManifest:
    ...
```

### Required validation rules

Each loaded plugin must pass all of the following checks before becoming active:

1. `plugin_id` matches `author/hc-{code}`
2. `version` is a valid semver-like version string
3. `min_hc_version` is compatible with the current `hybrid-coco` version
4. `languages` is not empty
5. each `LanguageSpec.name` is non-empty and normalized
6. each `LanguageSpec.extensions` is non-empty
7. each language defines all structure query kinds:
   - `function`
   - `method`
   - `class`
   - `import`
8. `parser_factory()` returns a valid `Parser`
9. `load_ts()` returns a valid `tree_sitter.Language`
10. extensions must be unique within the active merged registry

If any rule fails, the plugin is rejected and reported by `hc plugin doctor`.

---

## Proposed runtime architecture

### New modules

#### `src/hybrid_coco/languages/contract.py`

Contains public plugin manifest types and validation helpers.

#### `src/hybrid_coco/languages/plugins.py`

Responsible for:

- discovering entry points
- loading manifests
- validating manifests
- reading and writing plugin install metadata
- resolving which plugin is active for a language

### Changes to `src/hybrid_coco/languages/registry.py`

Refactor the current static registry into two layers:

1. core registry
2. merged active registry

Suggested shape:

```python
CORE_LANGUAGE_SPECS: tuple[LanguageSpec, ...] = (...)

ACTIVE_LANGUAGE_SPECS: tuple[LanguageSpec, ...] = build_active_specs()
```

Derived structures should come from the active registry:

- `_SPECS_BY_NAME`
- `EXTENSION_MAP`
- `KNOWN_LANGUAGES`

The module should expose an explicit reload hook:

```python
def reload_registry() -> None:
    ...
```

That function must rebuild:

- active specs
- language lookup maps
- extension map

### Cache invalidation

Any plugin install or uninstall must invalidate:

- parser cache in `src/hybrid_coco/parsers/__init__.py`
- structure parser and query caches in `src/hybrid_coco/structure.py`

This should happen through explicit functions, not import side effects.

---

## Conflict resolution model

Conflict resolution is per language code.

### Rule

For a given language, the winning implementation is:

- the most recently installed valid plugin for that language

If the active plugin is removed:

- the next most recent valid plugin becomes active
- otherwise the built-in core implementation becomes active if it exists
- otherwise the language disappears from the active registry

### Why installation time instead of version number

Version ordering alone is not enough because:

- different authors may publish different implementations for the same language
- a user may intentionally install an older package after a newer one to force replacement

The system therefore needs a persisted installation order.

### Persisted plugin state

Store plugin activation metadata in:

- `.hybrid-coco/plugins.toml`

Suggested structure:

```toml
[[plugins]]
id = "acme/hc-ruby"
distribution = "hc-ruby"
version = "2.1.0"
language = "ruby"
installed_at = "2026-08-18T08:53:00Z"

[[plugins]]
id = "other/hc-ruby"
distribution = "other-hc-ruby"
version = "1.4.0"
language = "ruby"
installed_at = "2026-08-17T10:15:00Z"
```

The active implementation for `ruby` is whichever valid plugin entry has the latest `installed_at`.

### Scope decision still open

The repo has not yet decided whether this file should be:

- project-local only
- user-global only
- or merged from both scopes

The safest default for team reproducibility is project-local metadata.

---

## Install and uninstall lifecycle

Introduce a new CLI group:

```text
hc plugin ...
```

### Proposed commands

#### `hc plugin list`

Shows:

- core languages
- installed plugins
- active plugin per language
- inactive superseded plugins

#### `hc plugin install <distribution>`

Flow:

1. install Python distribution with pip
2. rediscover entry points
3. load returned manifest
4. validate the contract
5. persist metadata in `.hybrid-coco/plugins.toml`
6. rebuild the registry
7. clear caches
8. report whether reindexing is recommended

#### `hc plugin uninstall <plugin-id>`

Flow:

1. resolve plugin metadata by canonical plugin id
2. uninstall the Python distribution
3. remove persisted metadata
4. rebuild winner selection for affected languages
5. clear caches
6. report the newly active implementation, if any

#### `hc plugin doctor`

Reports:

- malformed manifests
- incompatible `min_hc_version`
- missing entry points
- orphaned plugin metadata
- invalid or colliding extensions
- superseded plugins

### Reindex expectations

Plugin install or uninstall does not itself need to reindex automatically. It should:

- keep the registry consistent immediately
- tell the user whether an `hc update` or `hc index` is required to refresh symbols for affected files

This avoids hidden expensive work during package management commands.

---

## Integration points in the current codebase

### `src/hybrid_coco/settings.py`

Today, extension overrides only accept names from static `KNOWN_LANGUAGES`.

This must change so that validation happens against the active merged registry, not only the built-in language set.

### `src/hybrid_coco/parsers/__init__.py`

Current parser cache:

```python
_PARSERS: dict[str, Parser] = {}
```

This cache must be explicitly reset after plugin changes, because the parser implementation for a language may have changed.

### `src/hybrid_coco/structure.py`

Structure queries and tree-sitter parsers are cached. They must be invalidated when:

- a plugin becomes active
- a plugin is removed
- a different plugin replaces the current winner for a language

### `src/hybrid_coco/indexer.py`

No architectural rewrite should be necessary. It already depends on the registry abstractions instead of hardcoding per-language behavior.

### `src/hybrid_coco/store.py`

No schema change should be necessary. The database stores the resolved language string and extracted symbols. A plugin only changes how that language is parsed, not the storage model.

### `src/hybrid_coco/server.py` and CLI query surface

No MCP tool rename is needed. Existing tools continue working because they depend on the active language registry indirectly.

---

## Override semantics against core languages

This is an open product decision and should be explicitly settled before implementation.

### Option A: plugins may only add new languages

Pros:

- lower risk
- built-in language behavior remains stable
- easier support expectations

Cons:

- impossible to hotfix or experiment with improved parsers for built-in languages

### Option B: plugins may replace built-in languages

Pros:

- maximum flexibility
- allows faster iteration for improved parsers
- useful for ecosystem-maintained grammars

Cons:

- active behavior becomes more dynamic
- parser regressions become easier to introduce
- more cache and compatibility edge cases

At analysis time, option B best matches the requested rule:

- the most recent plugin for the same language replaces the previous one

If adopted, replacement should still be explicit and visible in `hc plugin list`.

---

## Example plugin package

Example repository layout for a Ruby plugin:

```text
hc-ruby/
├── pyproject.toml
├── hc_ruby/
│   ├── __init__.py
│   └── parser.py
└── tests/
    └── test_parser.py
```

### Example `pyproject.toml`

```toml
[project]
name = "hc-ruby"
version = "1.0.0"
dependencies = [
  "hybrid-coco>=0.3.0",
  "tree-sitter>=0.23.0",
  "tree-sitter-ruby>=0.23.0",
]

[project.entry-points."hybrid_coco.languages"]
"acme/hc-ruby" = "hc_ruby:register"
```

### Example registration function

```python
from hybrid_coco.languages.contract import LanguagePluginManifest
from hybrid_coco.languages.registry import LanguageSpec


def register() -> LanguagePluginManifest:
    return LanguagePluginManifest(
        plugin_id="acme/hc-ruby",
        version="1.0.0",
        min_hc_version="0.3.0",
        distribution="hc-ruby",
        languages=(
            LanguageSpec(
                name="ruby",
                extensions=(".rb", ".rake", ".gemspec"),
                load_ts=_load_ruby,
                parser_factory=_ruby_parser,
                structure_queries={
                    "function": "...",
                    "method": "...",
                    "class": "...",
                    "import": "...",
                },
            ),
        ),
    )
```

---

## Testing strategy

Add a dedicated test module:

- `tests/test_plugins.py`

Coverage should include:

1. valid plugin discovery through entry points
2. rejection of malformed plugin ids
3. rejection of incompatible `min_hc_version`
4. replacement of one plugin by a more recently installed plugin for the same language
5. uninstall restoring the previous valid implementation
6. merged `KNOWN_LANGUAGES` including plugin languages
7. extension override validation accepting plugin-defined languages
8. parser cache invalidation
9. structure cache invalidation
10. plugin doctor reporting invalid state clearly

Existing registry tests should be split so they can assert both:

- core registry invariants
- active merged registry invariants

---

## Migration plan

### Phase 16a

Introduce:

- `languages/contract.py`
- plugin discovery through entry points
- merged active registry

No CLI install/uninstall yet. This phase proves the architecture.

### Phase 16b

Introduce:

- `.hybrid-coco/plugins.toml`
- persisted install ordering
- conflict resolution by `installed_at`

### Phase 16c

Introduce:

- `hc plugin list`
- `hc plugin install`
- `hc plugin uninstall`
- `hc plugin doctor`

### Phase 16d

Create one external reference plugin, for example:

- `hc-zig`

This validates the contract outside the core repo.

### Phase 16e

Document operational guidance in README and maintainer docs once the implementation is stable.

---

## Explicit non-goals

This architecture does not introduce:

- a hosted plugin marketplace inside `hybrid-coco`
- automatic background updates of plugins
- hidden fallback behavior when a contract is incomplete
- new MCP tool names
- mandatory plugin usage for common languages
- any non-SQLite persistence layer

---

## Open decisions

These points were identified during analysis and remain intentionally open:

1. can plugins override built-in core languages or only add new ones
2. should plugin metadata be project-local, global, or hybrid
3. should distribution naming be free or follow a stronger anti-collision prefix
4. should the first implementation step be infrastructure only or the complete CLI lifecycle

---

## Recommended direction

If implementation starts later in a new conversation, the recommended order is:

1. refactor `registry.py` into core plus active merged registry
2. add explicit plugin manifest types and validation
3. add persistent install metadata and deterministic winner selection
4. add cache invalidation hooks
5. add CLI lifecycle commands
6. add one external reference plugin to validate the contract end-to-end

This sequence keeps risk contained while preserving the current user-facing behavior of the core package.
