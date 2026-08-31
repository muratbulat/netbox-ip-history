# Changelog

All notable changes to this project will be documented here.

## [0.3.3] - 2026-09-01

Removed a duplicate `release.yml` CI workflow that published to PyPI on tag
push with no verification, bypassing `publish-pypi.yml`'s verify-gated
publish job. No functional changes to the plugin itself.

## [0.3.2] - 2026-08-31

Republish of the 0.3.1 baseline under a new version number; 0.3.1 could not
be published to PyPI because its filenames were previously used and deleted
(PyPI never allows filename reuse). No functional changes from 0.3.1.

## [0.3.1] - 2026-08-31

Initial public baseline.
