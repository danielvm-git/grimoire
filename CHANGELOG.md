## [0.8.1](https://github.com/danielvm-git/grimoire/compare/v0.8.0...v0.8.1) (2026-08-03)


### Bug Fixes

* **checks:** pin master default branch for master-default repos ([021b964](https://github.com/danielvm-git/grimoire/commit/021b9649d61e9b0c37d98c714f4996d3221ffd3d))

# [0.8.0](https://github.com/danielvm-git/grimoire/compare/v0.7.1...v0.8.0) (2026-08-02)


### Features

* **release:** finalize e11 end-to-end browser testing epic ([f6481c1](https://github.com/danielvm-git/grimoire/commit/f6481c1d84d0a791132c419283cc17a182ef8156))

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

