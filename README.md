# Collection Link Panel

Blender 4.2+ extension for viewing and editing collection links in Collection and Scene Properties.

## Review and Testing

After installing and enabling the extension, its panels are available at:

- `Properties > Collection > Links`
- `Properties > Scene > Collections`

## Collection Status

Link search menus show these markers to the left of collection names:

- `0`: zero users (unused data)
- `F`: Fake User is enabled
- `L`: linked from a library
- `O` (uppercase letter): a Library Override

Panels show the corresponding status icons without letter or number markers.
Names of library-linked collections, Library Overrides, and other non-editable
collections are displayed as labels rather than text fields. Editable local
collections without overrides retain their name fields.
Search menus retain the collection
or scene icon and prefix the displayed name with the markers (for example,
`L  Collection`). Library/override status precedes Fake User/unused status, as in
Blender's data-block menus. Results remain sorted by collection name. These markers do not
change the actual collection names. The `0` marker follows Blender's user count;
a collection used by an instance can have no parents and still have users.

## Releases

Push a tag matching `v` plus the version in `blender_manifest.toml` to build and publish a GitHub Release. For example, after updating both the manifest version and `bl_info["version"]`:

```sh
git tag v1.0.2
git push origin v1.0.2
```

The release workflow runs the tests, builds and validates the extension with Blender, and attaches an installable ZIP. The ZIP contains only `__init__.py`, `blender_manifest.toml`, and `LICENSE`; tests and workflow files stay in the source repository.
