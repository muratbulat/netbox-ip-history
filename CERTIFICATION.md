# NetBox Labs Plugin Certification Readiness

This is a readiness checklist, not a certification claim. NetBox Labs certification is external and release-specific.

| Requirement | Status | Evidence |
| --- | --- | --- |
| GitHub-hosted public repository | PASS | https://github.com/muratbulat/netbox-ip-history |
| OSI-approved license | PASS | `LICENSE`, Apache-2.0 metadata |
| PyPI package | PASS | Published: https://pypi.org/project/netbox-ip-history/ |
| Compatibility metadata | PASS | `README.md`, `COMPATIBILITY.md`, `PluginConfig` range |
| Real NetBox compatibility matrix | PASS | Verified against NetBox Community v4.6.8 / Python 3.14 / Django 6.0.8, plus v4.4.10 and v4.5.10; see `COMPATIBILITY.md` for the full matrix |
| Comprehensive tests | PASS | Unit tests pass locally and against a real NetBox/Django environment in CI (`netbox-matrix.yml`) |
| GitHub Actions | PASS | CI, matrix, build, security, and PyPI publish workflows are defined |
| Documentation | PASS | README EN/TR, Wiki source, guides, release notes |
| Screenshots | PASS | High-resolution 1080p screenshots included in `docs/assets/screenshots/` |
| Original icon | PASS | `docs/assets/icon.svg`, CC BY 4.0 asset license |
| Release notes | PASS | Documented in `CHANGELOG.md`; see [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) for the release process |
| Security policy | PASS | `SECURITY.md`, `docs/SECURITY-REVIEW.md` |
| Dependencies documented | PASS | README dependency section and package metadata |
| Release artifacts | PASS | GitHub Releases attach the built wheel and sdist (see `tools/verify_release.py` for automated content verification) |
| Plugin Catalog submission | PARTIAL | Draft prepared; external review/listing not yet requested |
| Certification application | PARTIAL | Draft prepared; external review remains unavailable |
| NetBox Labs co-maintainer relationship | BLOCKED | Requires coordination with NetBox Labs after application |

No badge or wording in this repository claims NetBox Labs certification.
