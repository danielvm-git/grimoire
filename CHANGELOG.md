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
