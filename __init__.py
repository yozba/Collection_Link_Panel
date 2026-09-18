# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Collection Link Panel",
    "author": "yozba",
    "description": "Display and edit collection links in Collection and Scene properties",
    "blender": (4, 2, 0),
    "version": (1, 0, 2),
    "location": "Properties > Collection, Scene",
    "warning": "",
    "category": "Scene",
}

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator, Panel


def _scene_roots():
    return (scene.collection for scene in bpy.data.scenes)


def _find_collection(uid):
    if not uid:
        return None
    for collection in bpy.data.collections:
        if str(collection.session_uid) == uid:
            return collection
    for root in _scene_roots():
        if str(root.session_uid) == uid:
            return root
    return None


def _contains_child(parent, child):
    return any(item == child for item in parent.children)


def _parents_of(collection):
    # Only collection users and collection links are relevant. Filtering both
    # sides avoids converting object references to Python IDs.
    users = bpy.data.user_map(
        subset={collection}, key_types={'COLLECTION'}, value_types={'COLLECTION'}
    ).get(collection, set())
    parents = {
        user for user in users
        if isinstance(user, bpy.types.Collection) and _contains_child(user, collection)
    }
    parents.update(root for root in _scene_roots() if _contains_child(root, collection))
    return sorted(parents, key=lambda item: item.name.casefold())


def _would_cycle(parent, child):
    if parent == child:
        return True
    stack = [child]
    visited = set()
    while stack:
        current = stack.pop()
        uid = current.session_uid
        if uid in visited:
            continue
        visited.add(uid)
        for descendant in current.children:
            if descendant == parent:
                return True
            stack.append(descendant)
    return False


def _descendant_uids(collection):
    visited = set()
    stack = [collection]
    while stack:
        current = stack.pop()
        uid = current.session_uid
        if uid in visited:
            continue
        visited.add(uid)
        stack.extend(current.children)
    return visited


def _ancestor_uids(collection, collections):
    parents_by_child = {}
    for parent in collections:
        for child in parent.children:
            parents_by_child.setdefault(child.session_uid, set()).add(parent.session_uid)

    visited = set()
    stack = [collection.session_uid]
    while stack:
        uid = stack.pop()
        if uid in visited:
            continue
        visited.add(uid)
        stack.extend(parents_by_child.get(uid, ()))
    return visited


def _collection_label(collection):
    for scene in bpy.data.scenes:
        if scene.collection == collection:
            return "Scene Collection: " + scene.name
    return collection.name


def _collection_icon(collection):
    if collection.is_embedded_data:
        return 'SCENE_DATA'
    if collection.color_tag != 'NONE':
        return 'COLLECTION_' + collection.color_tag
    return 'OUTLINER_COLLECTION'


def _tag_properties_redraw(context):
    if context is None:
        return
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()


# Blender keeps references to dynamic enum strings only while the callback is
# alive. Retain the item list for the lifetime of the search popup.
_search_items = []


def _link_targets(operator, context):
    global _search_items
    source = _find_collection(operator.source_uid)
    if source is None:
        _search_items = []
        return _search_items

    collections = list(bpy.data.collections)
    candidates = [(collection, collection.name) for collection in collections]
    if operator.direction == 'PARENT':
        if source.is_embedded_data:
            _search_items = []
            return _search_items
        candidates.extend(
            (scene.collection, "Scene Collection: " + scene.name)
            for scene in bpy.data.scenes
        )
        cycle_uids = _descendant_uids(source)
        linked_uids = {parent.session_uid for parent in _parents_of(source)}
    else:
        if not source.is_editable:
            _search_items = []
            return _search_items
        cycle_uids = _ancestor_uids(source, collections)
        linked_uids = {child.session_uid for child in source.children}

    _search_items = []
    for candidate, label in candidates:
        if candidate.session_uid in cycle_uids or candidate.session_uid in linked_uids:
            continue
        parent, child = ((candidate, source) if operator.direction == 'PARENT'
                         else (source, candidate))
        if child.is_embedded_data or not parent.is_editable:
            continue
        _search_items.append((str(candidate.session_uid), label, "", _collection_icon(candidate)))
    _search_items.sort(key=lambda item: item[1].casefold())
    _search_items = [(*item, index) for index, item in enumerate(_search_items)]
    return _search_items


class COLLECTION_OT_link(Operator):
    """Link the active collection to an existing parent or child"""

    bl_idname = "collection.link_panel_link"
    bl_label = "Link Collection"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "target_uid"

    source_uid: StringProperty(options={'HIDDEN'})
    direction: EnumProperty(
        items=(('PARENT', "Link to Parent", ""),
               ('CHILD', "Link Child", "")),
        options={'HIDDEN'},
    )
    target_uid: EnumProperty(name="Collection", items=_link_targets)

    def invoke(self, context, event):
        if not self.source_uid and context.collection:
            self.source_uid = str(context.collection.session_uid)
        if _find_collection(self.source_uid) is None:
            return {'CANCELLED'}
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        source = _find_collection(self.source_uid)
        target = _find_collection(self.target_uid)
        if source is None or target is None:
            self.report({'WARNING'}, "Collection no longer exists")
            return {'CANCELLED'}
        parent, child = ((target, source) if self.direction == 'PARENT'
                         else (source, target))
        if not parent.is_editable:
            self.report({'WARNING'}, "Parent collection is not editable")
            return {'CANCELLED'}
        if child.is_embedded_data:
            self.report({'WARNING'}, "Scene root collections cannot be linked as children")
            return {'CANCELLED'}
        if _contains_child(parent, child):
            self.report({'WARNING'}, "Collections are already linked")
            return {'CANCELLED'}
        if _would_cycle(parent, child):
            self.report({'WARNING'}, "Link would create a cycle")
            return {'CANCELLED'}
        try:
            parent.children.link(child)
        except (RuntimeError, TypeError, ValueError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        _tag_properties_redraw(context)
        return {'FINISHED'}


class COLLECTION_OT_create_linked(Operator):
    """Create a collection and link it as a parent or child"""

    bl_idname = "collection.link_panel_create_linked"
    bl_label = "Create Linked Collection"
    bl_options = {'REGISTER', 'UNDO'}

    source_uid: StringProperty(options={'HIDDEN'})
    direction: EnumProperty(
        items=(('PARENT', "New Parent", ""),
               ('CHILD', "New Child", "")),
        options={'HIDDEN'},
    )

    def execute(self, context):
        source = _find_collection(self.source_uid)
        if source is None:
            self.report({'WARNING'}, "Collection no longer exists")
            return {'CANCELLED'}
        if self.direction == 'PARENT':
            if source.is_embedded_data:
                self.report({'WARNING'}, "Scene root collections cannot be linked as children")
                return {'CANCELLED'}
        elif not source.is_editable:
            self.report({'WARNING'}, "Parent collection is not editable")
            return {'CANCELLED'}

        new_collection = bpy.data.collections.new("Collection")
        try:
            if self.direction == 'PARENT':
                new_collection.children.link(source)
            else:
                source.children.link(new_collection)
        except (RuntimeError, TypeError, ValueError) as exc:
            bpy.data.collections.remove(new_collection)
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        if self.direction == 'PARENT':
            new_collection.use_fake_user = True
        _tag_properties_redraw(context)
        return {'FINISHED'}


class COLLECTION_OT_unlink(Operator):
    """Remove one parent-child link without deleting either collection"""

    bl_idname = "collection.link_panel_unlink"
    bl_label = "Unlink Collection"
    bl_options = {'REGISTER', 'UNDO'}

    parent_uid: StringProperty(options={'HIDDEN'})
    child_uid: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        parent = _find_collection(self.parent_uid)
        child = _find_collection(self.child_uid)
        if parent is None or child is None or not _contains_child(parent, child):
            self.report({'WARNING'}, "Collection link no longer exists")
            return {'CANCELLED'}
        if not parent.is_editable:
            self.report({'WARNING'}, "Parent collection is not editable")
            return {'CANCELLED'}
        try:
            parent.children.unlink(child)
        except (RuntimeError, TypeError, ValueError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        if child.users == 0:
            if child.is_editable:
                child.use_fake_user = True
                self.report({'INFO'}, "Unlinked collection kept with Fake User")
            else:
                self.report({'WARNING'}, "Unlinked collection has no users")
        _tag_properties_redraw(context)
        return {'FINISHED'}


class COLLECTION_PT_LinkProperties(Panel):
    """Collection links"""

    bl_label = "Links"
    bl_idname = "COLLECTION_PT_link_properties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    @classmethod
    def poll(cls, context):
        return context.collection is not None

    def draw(self, context):
        pass


class COLLECTION_PT_CollectionLinking(Panel):
    """Collections containing the active collection"""

    bl_label = "Parents"
    bl_idname = "COLLECTION_PT_collection_linking"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"
    bl_parent_id = "COLLECTION_PT_link_properties"

    def draw(self, context):
        layout = self.layout
        collection = context.collection
        row = layout.row(align=True)
        op = row.operator(COLLECTION_OT_link.bl_idname, text="Link to Parent")
        op.source_uid = str(collection.session_uid)
        op.direction = 'PARENT'
        button = row.row(align=True)
        button.enabled = not collection.is_embedded_data
        op = button.operator(COLLECTION_OT_create_linked.bl_idname, text="", icon='ADD')
        op.source_uid = str(collection.session_uid)
        op.direction = 'PARENT'

        parents = _parents_of(collection)
        for parent in parents:
            row = layout.box().row()
            if parent.is_embedded_data:
                row.label(text=_collection_label(parent), icon=_collection_icon(parent))
            else:
                row.prop(parent, "name", text="", icon=_collection_icon(parent))
            button = row.row()
            button.enabled = parent.is_editable
            op = button.operator(COLLECTION_OT_unlink.bl_idname, text="", icon='X', emboss=False)
            op.parent_uid = str(parent.session_uid)
            op.child_uid = str(collection.session_uid)


class COLLECTION_PT_CollectionLinked(Panel):
    """Collections directly linked under the active collection"""

    bl_label = "Children"
    bl_idname = "COLLECTION_PT_collection_linked"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"
    bl_parent_id = "COLLECTION_PT_link_properties"

    def draw(self, context):
        _draw_children(self.layout, context.collection)


def _draw_children(layout, collection):
    row = layout.row(align=True)
    row.enabled = collection.is_editable
    op = row.operator(COLLECTION_OT_link.bl_idname, text="Link Child")
    op.source_uid = str(collection.session_uid)
    op.direction = 'CHILD'
    op = row.operator(COLLECTION_OT_create_linked.bl_idname, text="", icon='ADD')
    op.source_uid = str(collection.session_uid)
    op.direction = 'CHILD'

    for child in collection.children:
        row = layout.box().row()
        row.prop(child, "name", text="", icon=_collection_icon(child))
        button = row.row()
        button.enabled = collection.is_editable
        op = button.operator(COLLECTION_OT_unlink.bl_idname, text="", icon='X', emboss=False)
        op.parent_uid = str(collection.session_uid)
        op.child_uid = str(child.session_uid)


class SCENE_PT_LinkCollections(Panel):
    """Collections directly linked under the active scene"""

    bl_label = "Collections"
    bl_idname = "SCENE_PT_link_panel_collections"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def draw(self, context):
        _draw_children(self.layout, context.scene.collection)


_classes = (
    COLLECTION_OT_link,
    COLLECTION_OT_create_linked,
    COLLECTION_OT_unlink,
    COLLECTION_PT_LinkProperties,
    COLLECTION_PT_CollectionLinking,
    COLLECTION_PT_CollectionLinked,
    SCENE_PT_LinkCollections,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
