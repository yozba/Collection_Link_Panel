# Collection Link Panel

Blender 4.2+ extension for viewing and editing collection links in Collection and Scene Properties.

## Releases

Push a tag matching `v` plus the version in `blender_manifest.toml` to build and publish a GitHub Release. For example, after updating both the manifest version and `bl_info["version"]`:

```sh
git tag v1.0.1
git push origin v1.0.1
```

The release workflow runs the tests, builds and validates the extension with Blender, and attaches an installable ZIP. The ZIP contains only `__init__.py`, `blender_manifest.toml`, and `LICENSE`; tests and workflow files stay in the source repository.
