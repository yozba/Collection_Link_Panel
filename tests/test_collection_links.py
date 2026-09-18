"""Behavior checks that run without an installed Blender binary."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest


class Children(list):
    def link(self, child):
        if child in self:
            raise RuntimeError("Already linked")
        self.append(child)
        child.users += 1

    def unlink(self, child):
        self.remove(child)
        child.users -= 1


class Collection:
    next_uid = 1

    def __init__(self, name, editable=True):
        self.name = name
        self.is_editable = editable
        self.is_embedded_data = False
        self.color_tag = 'NONE'
        self.children = Children()
        self.users = 0
        self.use_fake_user = False
        self.session_uid = Collection.next_uid
        Collection.next_uid += 1


class Collections(list):
    def new(self, name):
        collection = Collection(name)
        self.append(collection)
        return collection


class Operator:
    def report(self, level, message):
        self.last_report = (level, message)


class Panel:
    pass


class Area:
    def __init__(self, area_type):
        self.type = area_type
        self.redraw_count = 0

    def tag_redraw(self):
        self.redraw_count += 1


class Layout:
    def __init__(self):
        self.operators = []
        self.properties = []
        self.enabled = True

    def row(self, **kwargs):
        return self

    def box(self):
        return self

    def prop(self, item, property_name, **kwargs):
        self.properties.append((item, property_name))

    def operator(self, idname, **kwargs):
        op = types.SimpleNamespace()
        self.operators.append((idname, op))
        return op


class Data:
    def __init__(self):
        self.collections = Collections()
        self.scenes = []
        self.user_map_calls = 0

    def user_map(self, *, subset, key_types, value_types):
        self.user_map_calls += 1
        self.user_map_filters = (key_types, value_types)
        child = next(iter(subset))
        users = {parent for parent in self.collections if child in parent.children}
        return {child: users}


def load_addon():
    bpy = types.ModuleType("bpy")
    bpy.data = Data()
    bpy_types = types.ModuleType("bpy.types")
    bpy_types.Collection = Collection
    bpy_types.Operator = Operator
    bpy_types.Panel = Panel
    bpy.types = bpy_types
    bpy.utils = types.SimpleNamespace(register_class=lambda cls: None,
                                      unregister_class=lambda cls: None)
    props = types.ModuleType("bpy.props")
    props.EnumProperty = lambda **kwargs: None
    props.StringProperty = lambda **kwargs: None
    sys.modules["bpy"] = bpy
    sys.modules["bpy.props"] = props
    sys.modules["bpy.types"] = bpy_types
    spec = importlib.util.spec_from_file_location(
        "collection_link_panel", Path(__file__).resolve().parents[1] / "__init__.py"
    )
    addon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(addon)
    return addon, bpy.data


class CollectionLinkTests(unittest.TestCase):
    def setUp(self):
        self.addon, self.data = load_addon()

    def test_parents_include_other_collections_and_scene_root(self):
        child = Collection("Child")
        parent = Collection("Parent")
        root = Collection("Scene Root")
        parent.children.link(child)
        root.children.link(child)
        self.data.collections = [child, parent]
        self.data.scenes = [types.SimpleNamespace(name="Scene", collection=root)]

        self.assertEqual(set(self.addon._parents_of(child)), {parent, root})
        self.assertEqual(self.data.user_map_calls, 1)
        self.assertEqual(self.data.user_map_filters, ({'COLLECTION'}, {'COLLECTION'}))

    def test_link_rejects_cycle_and_unlink_preserves_orphan(self):
        parent = Collection("Parent")
        child = Collection("Child")
        parent.children.link(child)
        self.data.collections = [parent, child]

        link = self.addon.COLLECTION_OT_link()
        link.source_uid = str(child.session_uid)
        link.target_uid = str(parent.session_uid)
        link.direction = 'CHILD'
        self.assertEqual(link.execute(None), {'CANCELLED'})
        self.assertEqual(len(child.children), 0)

        unlink = self.addon.COLLECTION_OT_unlink()
        unlink.parent_uid = str(parent.session_uid)
        unlink.child_uid = str(child.session_uid)
        self.assertEqual(unlink.execute(None), {'FINISHED'})
        self.assertTrue(child.use_fake_user)

    def test_link_to_existing_parent(self):
        parent = Collection("Parent")
        child = Collection("Child")
        self.data.collections = [parent, child]
        properties = Area('PROPERTIES')
        viewport = Area('VIEW_3D')
        context = types.SimpleNamespace(window_manager=types.SimpleNamespace(
            windows=[types.SimpleNamespace(screen=types.SimpleNamespace(
                areas=[properties, viewport]
            ))]
        ))
        link = self.addon.COLLECTION_OT_link()
        link.source_uid = str(child.session_uid)
        link.target_uid = str(parent.session_uid)
        link.direction = 'PARENT'

        self.assertEqual(link.execute(context), {'FINISHED'})
        self.assertIn(child, parent.children)
        self.assertEqual(properties.redraw_count, 1)
        self.assertEqual(viewport.redraw_count, 0)
        self.assertEqual(link.execute(context), {'CANCELLED'})
        self.assertEqual(properties.redraw_count, 1)

    def test_scene_root_cannot_be_linked_as_child(self):
        parent = Collection("Parent")
        root = Collection("Root")
        root.is_embedded_data = True
        self.data.collections = [parent]
        self.data.scenes = [types.SimpleNamespace(name="Scene", collection=root)]
        link = self.addon.COLLECTION_OT_link()
        link.source_uid = str(root.session_uid)
        link.target_uid = str(parent.session_uid)
        link.direction = 'PARENT'

        self.assertEqual(link.execute(None), {'CANCELLED'})
        self.assertNotIn(root, parent.children)

    def test_link_targets_exclude_cycles(self):
        ancestor = Collection("Ancestor")
        middle = Collection("Middle")
        descendant = Collection("Descendant")
        available = Collection("Available")
        ancestor.children.link(middle)
        middle.children.link(descendant)
        self.data.collections = [ancestor, middle, descendant, available]

        link = self.addon.COLLECTION_OT_link()
        link.source_uid = str(ancestor.session_uid)
        link.direction = 'PARENT'
        parent_targets = {item[0] for item in self.addon._link_targets(link, None)}
        self.assertNotIn(str(middle.session_uid), parent_targets)
        self.assertNotIn(str(descendant.session_uid), parent_targets)
        self.assertIn(str(available.session_uid), parent_targets)

        link.source_uid = str(descendant.session_uid)
        link.direction = 'CHILD'
        child_targets = {item[0] for item in self.addon._link_targets(link, None)}
        self.assertNotIn(str(ancestor.session_uid), child_targets)
        self.assertNotIn(str(middle.session_uid), child_targets)
        self.assertIn(str(available.session_uid), child_targets)

    def test_link_targets_exclude_existing_links(self):
        source = Collection("Source")
        parent = Collection("Parent")
        child = Collection("Child")
        available = Collection("Available")
        root = Collection("Scene Root")
        root.is_embedded_data = True
        parent.children.link(source)
        source.children.link(child)
        root.children.link(source)
        self.data.collections = [source, parent, child, available]
        self.data.scenes = [types.SimpleNamespace(name="Scene", collection=root)]

        link = self.addon.COLLECTION_OT_link()
        link.source_uid = str(source.session_uid)
        link.direction = 'PARENT'
        parent_targets = {item[0] for item in self.addon._link_targets(link, None)}
        self.assertEqual(parent_targets, {str(available.session_uid)})

        link.direction = 'CHILD'
        child_targets = {item[0] for item in self.addon._link_targets(link, None)}
        self.assertEqual(child_targets, {str(available.session_uid)})

    def test_link_targets_have_collection_and_scene_icons(self):
        child = Collection("Child")
        parent = Collection("Parent")
        parent.color_tag = 'COLOR_02'
        root = Collection("Scene Root")
        root.is_embedded_data = True
        self.data.collections = [child, parent]
        self.data.scenes = [types.SimpleNamespace(name="Other Scene", collection=root)]
        link = self.addon.COLLECTION_OT_link()
        link.source_uid = str(child.session_uid)
        link.direction = 'PARENT'

        items = self.addon._link_targets(link, None)
        by_uid = {item[0]: item for item in items}
        self.assertEqual(by_uid[str(parent.session_uid)][3], 'COLLECTION_COLOR_02')
        self.assertEqual(by_uid[str(root.session_uid)][3], 'SCENE_DATA')
        self.assertEqual([item[4] for item in items], list(range(len(items))))

    def test_create_parent_links_only_to_source(self):
        child = Collection("Child")
        root = Collection("Scene Root")
        self.data.collections.append(child)
        self.data.scenes = [types.SimpleNamespace(name="Scene", collection=root)]
        properties = Area('PROPERTIES')
        context = types.SimpleNamespace(
            scene=self.data.scenes[0],
            window_manager=types.SimpleNamespace(windows=[types.SimpleNamespace(
                screen=types.SimpleNamespace(areas=[properties])
            )]),
        )
        create = self.addon.COLLECTION_OT_create_linked()
        create.source_uid = str(child.session_uid)
        create.direction = 'PARENT'

        self.assertEqual(create.execute(context), {'FINISHED'})
        new_parent = self.data.collections[-1]
        self.assertIn(child, new_parent.children)
        self.assertNotIn(new_parent, root.children)
        self.assertTrue(new_parent.use_fake_user)
        self.assertEqual(properties.redraw_count, 1)

    def test_create_child_links_it_to_source(self):
        parent = Collection("Parent")
        self.data.collections.append(parent)
        context = types.SimpleNamespace(window_manager=types.SimpleNamespace(windows=[]))
        create = self.addon.COLLECTION_OT_create_linked()
        create.source_uid = str(parent.session_uid)
        create.direction = 'CHILD'

        self.assertEqual(create.execute(context), {'FINISHED'})
        new_child = self.data.collections[-1]
        self.assertIn(new_child, parent.children)

    def test_scene_panel_links_existing_and_new_children(self):
        root = Collection("Scene Root")
        root.is_embedded_data = True
        scene = types.SimpleNamespace(name="Scene", collection=root)
        self.data.scenes = [scene]
        existing = Collection("Existing")
        self.data.collections.append(existing)
        context = types.SimpleNamespace(
            scene=scene,
            window_manager=types.SimpleNamespace(windows=[]),
        )

        panel = self.addon.SCENE_PT_LinkCollections()
        panel.layout = Layout()
        panel.draw(context)
        self.assertEqual(panel.bl_context, 'scene')
        self.assertEqual(panel.bl_label, 'Collections')
        self.assertFalse(hasattr(panel, 'bl_parent_id'))
        link_button, create_button = [op for _, op in panel.layout.operators]
        self.assertEqual(link_button.source_uid, str(root.session_uid))
        self.assertEqual(link_button.direction, 'CHILD')
        self.assertEqual(create_button.source_uid, str(root.session_uid))
        self.assertEqual(create_button.direction, 'CHILD')

        link = self.addon.COLLECTION_OT_link()
        link.source_uid = link_button.source_uid
        link.direction = link_button.direction
        link.target_uid = str(existing.session_uid)
        self.assertEqual(link.execute(context), {'FINISHED'})
        self.assertIn(existing, root.children)

        panel.layout = Layout()
        panel.draw(context)
        self.assertIn((existing, "name"), panel.layout.properties)
        unlink_button = panel.layout.operators[-1][1]
        unlink = self.addon.COLLECTION_OT_unlink()
        unlink.parent_uid = unlink_button.parent_uid
        unlink.child_uid = unlink_button.child_uid
        self.assertEqual(unlink.execute(context), {'FINISHED'})
        self.assertNotIn(existing, root.children)

        create = self.addon.COLLECTION_OT_create_linked()
        create.source_uid = create_button.source_uid
        create.direction = create_button.direction
        self.assertEqual(create.execute(context), {'FINISHED'})
        self.assertIn(self.data.collections[-1], root.children)


if __name__ == "__main__":
    unittest.main()
