## [0.8.1](https://github.com/danielvm-git/grimoire/compare/v0.8.0...v0.8.1) (2026-08-03)


### Bug Fixes

* **checks:** pin master default branch for master-default repos ([021b964](https://github.com/danielvm-git/grimoire/commit/021b9649d61e9b0c37d98c714f4996d3221ffd3d))

# [0.8.0](https://github.com/danielvm-git/grimoire/compare/v0.7.1...v0.8.0) (2026-08-02)


### Features

* **release:** finalize e11 end-to-end browser testing epic ([f6481c1](https://github.com/danielvm-git/grimoire/commit/f6481c1d84d0a791132c419283cc17a182ef8156))

## [0.19.0] - 2026-11-09

### Features

- **checks:** run every enabled check once at startup, then follow the schedule ([#73](https://github.com/danielvm-git/grimoire/issues/73)) ([c16bce9](https://github.com/danielvm-git/grimoire/commit/c16bce98441ffc1a55ec46b26f2bb88ded480085))

## [0.18.0] - 2026-11-09

### Features

- **config:** discover every repo of a user account with a user source ([#71](https://github.com/danielvm-git/grimoire/issues/71)) ([850000e](https://github.com/danielvm-git/grimoire/commit/850000e6c8d56302f1af3158201e9f6cebd89042))

## [0.17.2] - 2026-11-09

### Bug Fixes

- **web:** link dot-named repos through a proxy-safe query URL ([#70](https://github.com/danielvm-git/grimoire/issues/70)) ([82dbe60](https://github.com/danielvm-git/grimoire/commit/82dbe60bf62da1594cdcdec637f00c5a459a44d6))

## [0.17.1] - 2026-11-09

### Bug Fixes

- **web:** render skipped and neutral workflow runs as their own status ([#69](https://github.com/danielvm-git/grimoire/issues/69)) ([e990f6e](https://github.com/danielvm-git/grimoire/commit/e990f6e68833189ac7fe467e18f85cee4c3dd445))

## [0.17.0] - 2026-11-09

### Features

- **checks:** publish audit result as a commit status ([#68](https://github.com/danielvm-git/grimoire/issues/68)) ([516001b](https://github.com/danielvm-git/grimoire/commit/516001ba6289717641fa156a8155d7219e11fa1f))

## [0.16.1] - 2026-11-08

### Bug Fixes

- **checks:** audit re-execs under the server interpreter without PyYAML ([#67](https://github.com/danielvm-git/grimoire/issues/67)) ([042336b](https://github.com/danielvm-git/grimoire/commit/042336b589225b70eb23cd44a94f2d40b8c2134c))

## [0.16.0] - 2026-11-08

### Features

- **checks:** stable audit rule IDs and --json output ([#66](https://github.com/danielvm-git/grimoire/issues/66)) ([9f483c5](https://github.com/danielvm-git/grimoire/commit/9f483c53929ac71c9a5fa63b0b2e2fe58866fb22))

## [0.15.3] - 2026-11-08

### Bug Fixes

- **checks:** migration check gates deploy and allows CLI repos ([#65](https://github.com/danielvm-git/grimoire/issues/65)) ([481b41a](https://github.com/danielvm-git/grimoire/commit/481b41a6cbfa7e810a4113ec7539dbb91eacb5d0))

## [0.15.2] - 2026-11-08

### Bug Fixes

- **checks:** correct the CI/CD Pipeline Audit rules ([#64](https://github.com/danielvm-git/grimoire/issues/64)) ([3585a2a](https://github.com/danielvm-git/grimoire/commit/3585a2a2772cfe448843ae73a064ce5a9874ed00))

## [0.15.1] - 2026-11-08

### Bug Fixes

- **fix:** close post-epic review findings ([#63](https://github.com/danielvm-git/grimoire/issues/63)) ([34d3d0c](https://github.com/danielvm-git/grimoire/commit/34d3d0ccc9657be7e7fff07ca9c5b3e8af68d71a))

## [0.15.0] - 2026-11-08

### Features

- **checks:** enforce template P0/P1 patterns with a compliance score ([#61](https://github.com/danielvm-git/grimoire/issues/61)) ([faf591a](https://github.com/danielvm-git/grimoire/commit/faf591aa8ebb6d903251e4a4336645281828cc97))

## [0.14.0] - 2026-11-07

### Features

- **web:** run all checks for one repo from the detail page ([#48](https://github.com/danielvm-git/grimoire/issues/48)) ([41bc2d8](https://github.com/danielvm-git/grimoire/commit/41bc2d854c45792dd1da819d6373e01deebb5f6f))

## [0.13.0] - 2026-11-07

### Features

- **web:** copy agent prompts for repo pendencies ([#47](https://github.com/danielvm-git/grimoire/issues/47)) ([940f8d4](https://github.com/danielvm-git/grimoire/commit/940f8d4f00f949be5435868008b43c0b66917c19))

## [0.12.5] - 2026-11-07

### Bug Fixes

- **database:** enable WAL and retry locks so cache writes cannot abort a fetch ([#44](https://github.com/danielvm-git/grimoire/issues/44)) ([72c2c20](https://github.com/danielvm-git/grimoire/commit/72c2c20f5700f00f3ff6efc2b41849ac32e86f6d))

## [0.12.4] - 2026-11-06

### Bug Fixes

- **specs:** mark stale bug specs as resolved ([#43](https://github.com/danielvm-git/grimoire/issues/43)) ([ebb668d](https://github.com/danielvm-git/grimoire/commit/ebb668da5e43cb4d049e565e6e3da764c011e7de))

## [0.12.3] - 2026-11-06

### Bug Fixes

- **ci:** install uv in the release job before the lockfile step ([#41](https://github.com/danielvm-git/grimoire/issues/41)) ([68b4d16](https://github.com/danielvm-git/grimoire/commit/68b4d165d197ea7be13c9f11c0b95aae554ed3b2))

## [0.12.1] - 2026-11-06

### Bug Fixes

- **mcp:** close e12 post-epic review findings ([#39](https://github.com/danielvm-git/grimoire/issues/39)) ([9b4b83d](https://github.com/danielvm-git/grimoire/commit/9b4b83d88f48751a99b3e75831f64a8c9acc6325))

## [0.12.0] - 2026-11-06

### Features

- **mcp:** implement MCP server and query layer (e12) ([ff7825a](https://github.com/danielvm-git/grimoire/commit/ff7825afaf32e3194be9610eafa3f85fb367948f))

### Bug Fixes

- **mcp:** use constant-time token comparison and fix story traceability ([631e614](https://github.com/danielvm-git/grimoire/commit/631e61433455c23a8f7dbe3013d82f8a464c742f))

## [0.11.6] - 2026-11-04

### Fixed

- **audit:** close hidden state machine gaps ([44d5e4f](https://github.com/danielvm-git/grimoire/commit/44d5e4f2d496f89aa17729912568c383d98331cd))

## [0.11.5] - 2026-11-04

### Fixed

- **deploy:** force Python 3.13 in the deploy environment ([#36](https://github.com/danielvm-git/grimoire/issues/36)) ([7421bba](https://github.com/danielvm-git/grimoire/commit/7421bba89c8c98073f476dd4fee385a82582c09c))

## [0.11.4] - 2026-11-04

### Fixed

- **deploy:** skip uv sync at runtime ([#35](https://github.com/danielvm-git/grimoire/issues/35)) ([fcb4a3a](https://github.com/danielvm-git/grimoire/commit/fcb4a3ae3bdd26433425535246e361ca5a8d2e36))

## [0.11.3] - 2026-11-04

### Fixed

- **deploy:** launch the entrypoint via sh ([#34](https://github.com/danielvm-git/grimoire/issues/34)) ([261a6d0](https://github.com/danielvm-git/grimoire/commit/261a6d0efac9135eada688267d46d37766ede426))

## [0.11.2] - 2026-11-04

### Fixed

- **deploy:** start the app from the prebuilt venv ([#33](https://github.com/danielvm-git/grimoire/issues/33)) ([08490cd](https://github.com/danielvm-git/grimoire/commit/08490cd86712e72fe3c26e611936361eebb57a43))

## [0.11.1] - 2026-11-04

### Fixed

- **db:** migrate existing databases at startup for run lease columns ([#31](https://github.com/danielvm-git/grimoire/issues/31)) ([0ba3e7e](https://github.com/danielvm-git/grimoire/commit/0ba3e7e713e6837c099a517103a10b2f05ebee19))

## [0.11.0] - 2026-11-04

### Added

- **state:** explicit run lifecycle and hot-path hardening ([#30](https://github.com/danielvm-git/grimoire/issues/30)) ([420fa08](https://github.com/danielvm-git/grimoire/commit/420fa08547b4a41fb6498dc5920db9511dc41189))

## [0.10.2] - 2026-08-10

### Fixed

- **config:** support optional env placeholder default for mcp token ([#29](https://github.com/danielvm-git/grimoire/issues/29)) ([72d1073](https://github.com/danielvm-git/grimoire/commit/72d1073623a0360a28c245208b4f876f43f1fb00))

## [0.10.1] - 2026-08-10

### Fixed

- **web:** use explicit params kwarg in _exec_text to avoid nesting ([83152bf](https://github.com/danielvm-git/grimoire/commit/83152bff6898116ad8455db7fd5d21aaf6ddc23b))
- **web:** clamp time-ago, atomic config write, suppress SQLModel nag, export filter respect ([#27](https://github.com/danielvm-git/grimoire/issues/27)) ([7a6fcc3](https://github.com/danielvm-git/grimoire/commit/7a6fcc3f5d5fbf7ab86bbc73e42b7d56b7fc9db7))
- **config:** validate refresh_schedule cron at config load ([#26](https://github.com/danielvm-git/grimoire/issues/26)) ([3cb9f93](https://github.com/danielvm-git/grimoire/commit/3cb9f93b480c0523c7f7bf7458645043b870e3c8))
- **github:** retry 429 and re-request on mid-pagination 304 ([#25](https://github.com/danielvm-git/grimoire/issues/25)) ([81e2568](https://github.com/danielvm-git/grimoire/commit/81e2568dbb499bf4e643fb7f4f1c9afaec8ebd68))
- **github:** recover archived/default_branch from cache on 304 ([#24](https://github.com/danielvm-git/grimoire/issues/24)) ([21f443a](https://github.com/danielvm-git/grimoire/commit/21f443a0d3ef235fcef20e1c7b4be995335c2c41))
- **workspace:** reject path traversal in branch/owner/repo names ([#23](https://github.com/danielvm-git/grimoire/issues/23)) ([e3770e2](https://github.com/danielvm-git/grimoire/commit/e3770e21c18ef9b7689f71f8010ba0b5fd1fb8b9))
- **actions:** recover stale lockout on restart, cap subprocess output to 64KB ([#22](https://github.com/danielvm-git/grimoire/issues/22)) ([d9183ea](https://github.com/danielvm-git/grimoire/commit/d9183ea11b24a90f35b6eb6dcf58b8c8d03d4442))

### Removed

- **revert:** drop unset GRIMOIRE_MCP_TOKEN placeholder that crashed config load ([#28](https://github.com/danielvm-git/grimoire/issues/28)) ([68af287](https://github.com/danielvm-git/grimoire/commit/68af2872e9ab53c6094cb300967f4ff2d871d50e))

## [0.10.0] - 2026-08-04

### Added

- **config:** configure mcp section with env var placeholder ([b4b3568](https://github.com/danielvm-git/grimoire/commit/b4b35685bcac57217928fcad82c0c685692c21f1))

## [0.9.1] - 2026-08-04

### Fixed

- **checks:** update global schedule and check definitions to run hourly ([c925033](https://github.com/danielvm-git/grimoire/commit/c925033ead3818174036d4b2f31ffffffcbd9590))

## [0.9.0] - 2026-08-04

### Added

- **mcp:** add MCP server and check backlog queries ([f5587fa](https://github.com/danielvm-git/grimoire/commit/f5587faa1dfe222701c9fec776ad4617547891f9))

### Fixed

- **specs:** quote scalars and fix formatting in bug registry ([c559c1a](https://github.com/danielvm-git/grimoire/commit/c559c1a779242e30b8629a0fcd5f3a78756ae21f))

## [0.7.1](https://github.com/danielvm-git/grimoire/compare/v0.7.0...v0.7.1) (2026-07-31)


### Bug Fixes

* use --no-banner instead of deprecated --quiet flag for gitleaks ([33f4204](https://github.com/danielvm-git/grimoire/commit/33f4204f8e100a1f80dc84381fdbdf383d063a2e))

# [0.7.0](https://github.com/danielvm-git/grimoire/compare/v0.6.0...v0.7.0) (2026-07-30)


### Features

* **checks:** add composer.lock freshness check for PHP projects ([fbb01a6](https://github.com/danielvm-git/grimoire/commit/fbb01a61e437ca7f702d36f66108379731e57ccc))

# [0.6.0](https://github.com/danielvm-git/grimoire/compare/v0.5.4...v0.6.0) (2026-07-30)


### Features

* **checks:** add PHP support to lint-passes check ([536e473](https://github.com/danielvm-git/grimoire/commit/536e4739e0a385a14bb4afa68e02ea921bbf3e3d))

## [0.5.4](https://github.com/danielvm-git/grimoire/compare/v0.5.3...v0.5.4) (2026-07-30)


### Bug Fixes

* **checks:** run lint on every refresh and install Node for eslint ([03715f0](https://github.com/danielvm-git/grimoire/commit/03715f00477fcc66eee3aa3651928f57a9e1b1d0))

## [0.5.3](https://github.com/danielvm-git/grimoire/compare/v0.5.2...v0.5.3) (2026-07-30)


### Bug Fixes

* **config:** add 39 missing repos and remove 3 stale entries ([94dd8c4](https://github.com/danielvm-git/grimoire/commit/94dd8c4d10f8e03267b46d384d0d2f1e19b11563))

## [0.5.2](https://github.com/danielvm-git/grimoire/compare/v0.5.1...v0.5.2) (2026-07-30)


### Bug Fixes

* **qa:** resolve 26 bugs across all modules — concurrency, pagination, error handling ([bc8f81d](https://github.com/danielvm-git/grimoire/commit/bc8f81da649bfc71a3ea23bf404b93df4a9ca7a7))
* **qa:** resolve critical null timestamp, config validation, zombie process, and regex crash bugs ([297e15d](https://github.com/danielvm-git/grimoire/commit/297e15d9ce5ff723f33902ffd4c295212ea2790c))

## [0.5.1](https://github.com/danielvm-git/grimoire/compare/v0.5.0...v0.5.1) (2026-07-30)


### Bug Fixes

* **checks:** fix check script syntax errors, exclusions, and version bump automation ([6e5734e](https://github.com/danielvm-git/grimoire/commit/6e5734ebc25b4ad9551b093d6155b8c6476059c7))

# [0.5.0](https://github.com/danielvm-git/grimoire/compare/v0.4.0...v0.5.0) (2026-07-26)


### Bug Fixes

* add missing greenlet dependency for async SQLite engine ([cb656d0](https://github.com/danielvm-git/grimoire/commit/cb656d0ecae8d32c0d8c6483b4015cc117d5c36e))


### Features

* **checks:** add ci-cd-migration v3 pattern detector ([10cc555](https://github.com/danielvm-git/grimoire/commit/10cc5550f096c059ceaeb398bf74dda31a250a5c))
* **checks:** add fleet check portfolio (e09) ([df86a1f](https://github.com/danielvm-git/grimoire/commit/df86a1f9d994369f66ea7d7960b0daa2f08cb3e2))

# [0.4.0](https://github.com/danielvm-git/grimoire/compare/v0.3.9...v0.4.0) (2026-07-24)


### Features

* **checks:** add CI/CD pipeline audit check ([3df4db5](https://github.com/danielvm-git/grimoire/commit/3df4db5249b14b0e4cb644cab7276eb3eca225c0))

## [0.3.9](https://github.com/danielvm-git/grimoire/compare/v0.3.8...v0.3.9) (2026-07-13)


### Bug Fixes

* **assets:** replace favicon.ico with correct Grimoire book icon ([6e93fef](https://github.com/danielvm-git/grimoire/commit/6e93fefb0425d9ca794a2f896058efd5dd8ffe0a))


### Reverts

* **security:** remove CSP middleware — BigBase handles CSP ([4dc6289](https://github.com/danielvm-git/grimoire/commit/4dc628966a972ff48b7118736abf231b6595bfe7))

## [0.3.8](https://github.com/danielvm-git/grimoire/compare/v0.3.7...v0.3.8) (2026-07-13)


### Bug Fixes

* **config:** include config.yaml in repo so it deploys to BigBase ([c813587](https://github.com/danielvm-git/grimoire/commit/c8135878f4460e7096035fe1d2d9fc73b72ca42b))

## [0.3.7](https://github.com/danielvm-git/grimoire/compare/v0.3.6...v0.3.7) (2026-07-13)


### Bug Fixes

* **security:** add CSP middleware to allow external CDN resources ([cf0076e](https://github.com/danielvm-git/grimoire/commit/cf0076eb70303396a6cbcc22f822811767328a6a))

## [0.3.6](https://github.com/danielvm-git/grimoire/compare/v0.3.5...v0.3.6) (2026-07-13)


### Bug Fixes

* **deploy:** remove root JSON stub that shadowed dashboard route ([cfe916f](https://github.com/danielvm-git/grimoire/commit/cfe916f6c2e109f714ae95b1629c1983f2b94bc9))

## [0.3.5](https://github.com/danielvm-git/grimoire/compare/v0.3.4...v0.3.5) (2026-07-13)


### Bug Fixes

* **deploy:** read PORT env var in app.py for BigBase deployment ([44f7b20](https://github.com/danielvm-git/grimoire/commit/44f7b2016e1b6d464f707049352241992c6a429c))

## [0.3.4](https://github.com/danielvm-git/grimoire/compare/v0.3.3...v0.3.4) (2026-07-12)


### Bug Fixes

* **deploy:** bind to dual-stack IPv4+IPv6 for BigBase health checks ([8b4f6ff](https://github.com/danielvm-git/grimoire/commit/8b4f6ff212958e2f5d8197e7dc0b737cc85b2d59))

## [0.3.3](https://github.com/danielvm-git/grimoire/compare/v0.3.2...v0.3.3) (2026-07-12)


### Bug Fixes

* **deploy:** add uv.lock back for BigBase uv sync ([0ffb318](https://github.com/danielvm-git/grimoire/commit/0ffb318c56465b76b52cc0d0043733cba025f996))

## [0.3.2](https://github.com/danielvm-git/grimoire/compare/v0.3.1...v0.3.2) (2026-07-12)


### Bug Fixes

* **deploy:** remove uv.lock so BigBase uses pip install ([5e9eee8](https://github.com/danielvm-git/grimoire/commit/5e9eee845f52c2c3c5db539b0f502663dcd90909))

## [0.3.1](https://github.com/danielvm-git/grimoire/compare/v0.3.0...v0.3.1) (2026-07-12)


### Bug Fixes

* **deploy:** add uvicorn startup to app.py for BigBase deployment ([48fa7b5](https://github.com/danielvm-git/grimoire/commit/48fa7b54b5ad0f91b5bdf0e53ec3ec2ce1fbd68c))

# [0.3.0](https://github.com/danielvm-git/grimoire/compare/v0.2.1...v0.3.0) (2026-07-12)


### Features

* enable API docs at /api/docs endpoint ([1db77ea](https://github.com/danielvm-git/grimoire/commit/1db77eacd95c690bafd3212c2da1426edab63d12))

## [0.2.1](https://github.com/danielvm-git/grimoire/compare/v0.2.0...v0.2.1) (2026-07-12)


### Bug Fixes

* **ci:** configure pytest testpaths, vulture min-confidence, and add greenlet dep ([bb47371](https://github.com/danielvm-git/grimoire/commit/bb473712a7c74feb2ef5dc1ded482c1257c8f373))

# [0.2.0](https://github.com/danielvm-git/grimoire/compare/v0.1.8...v0.2.0) (2026-07-12)


### Bug Fixes

* add fallback FastAPI app for BigBase health check ([c20e6be](https://github.com/danielvm-git/grimoire/commit/c20e6be219d1d23be5c68c92e538e41dacd4e2b8))
* add setup.py for BigBase package metadata resolution ([e9d99d4](https://github.com/danielvm-git/grimoire/commit/e9d99d469c677f46d927a26212d4b9ba3f6e84ac))
* add src/ to PYTHONPATH in BigBase entrypoint ([f1b0371](https://github.com/danielvm-git/grimoire/commit/f1b0371ab659cc5ea17bdbda252c67f7d3902c45))
* add stderr logging to BigBase entrypoint ([650f60c](https://github.com/danielvm-git/grimoire/commit/650f60c8e5a19263e424e805a62d044be743b53c))
* **ci:** add build to dev dependencies for python -m build ([a542ca9](https://github.com/danielvm-git/grimoire/commit/a542ca93e767c93a97d79050ad564b2c47139c68))
* **ci:** add build-system to pyproject.toml so uv installs the local package ([d67521e](https://github.com/danielvm-git/grimoire/commit/d67521e00db0de193b1f174c33da19b7d1ad1ce1))
* **ci:** add dependency groups to pyproject.toml for uv sync ([89f7f29](https://github.com/danielvm-git/grimoire/commit/89f7f29ffbfe0bdc00df515083db126376882b4e))
* **ci:** add package discovery for uv sync to find grimoire module ([50af04f](https://github.com/danielvm-git/grimoire/commit/50af04f2dac442586b12c8c806c5a02ee243d9b0))
* **ci:** add pytest pythonpath to find grimoire module ([ffa54cf](https://github.com/danielvm-git/grimoire/commit/ffa54cf429bd8818f0eba4c23eb8d1240446920e))
* **ci:** set asyncio_mode=auto for pytest-asyncio ([649ce39](https://github.com/danielvm-git/grimoire/commit/649ce396eae502c5b45ae1641095b044316abb20))
* instantiate app at module level for BigBase auto-detection ([fadb1f1](https://github.com/danielvm-git/grimoire/commit/fadb1f1beb111c52aed422058ea0b811c28b39f5))
* move type ignore comment to correct line for pyright ([eff1dbb](https://github.com/danielvm-git/grimoire/commit/eff1dbb3816e922c43bb9904c0da0a1dd4c345d4))
* place type ignore on the correct line for pyright ([8d30d24](https://github.com/danielvm-git/grimoire/commit/8d30d2451e06642c97e82563a002d9200627b694))
* print traceback on BigBase startup failure ([be1637a](https://github.com/danielvm-git/grimoire/commit/be1637a7bce83ae5c50da631215d63c8f72f69e2))
* resolve ruff lint errors in app.py entry point ([8e566ae](https://github.com/danielvm-git/grimoire/commit/8e566ae6abf8b9f1e39a3554481dc90b521afc48))
* start minimal app first for health check, load full app async ([2621018](https://github.com/danielvm-git/grimoire/commit/2621018f27b390cbef1b38893c77ec6a73520c11))


### Features

* add BigBase entrypoints with PORT env var support ([31d5746](https://github.com/danielvm-git/grimoire/commit/31d5746b60d7ec807596f1677229fdc21d834416))
