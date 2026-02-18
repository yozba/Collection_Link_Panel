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
    "description": "Display linked collection relationships in the Collection properties panel",
    "blender": (4, 2, 0),
    "version": (1, 0, 0),
    "location": "Properties > Collection",
    "warning": "",
    "category": "Scene",
}

import bpy
from bpy.types import Panel, PropertyGroup, Collection
from bpy.props import CollectionProperty, PointerProperty, StringProperty

class COLLECTION_PT_LinkProperties(Panel):
    """Collection Link Panel"""
    bl_label = "Collection Link"
    bl_idname = "COLLECTION_PT_link_properties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context):
        layout = self.layout
        collection = context.collection
        
        if collection is None:
            layout.label(text="コレクションが選択されていません")
            return

        # リンク コレクション（親コレクション）
        box = layout.box()
        col = box.column()
        col.label(text="リンク コレクション", icon='LINKED')
        
        parent_count = 0
        for other_col in bpy.data.collections:
            if collection in other_col.children:
                parent_count += 1
                row = col.row()
                row.label(text=other_col.name, icon='OUTLINER_COLLECTION')
                # リンク解除ボタン
                row.operator(
                    'collection.unlink_parent',
                    text="",
                    icon='UNLINKED'
                ).collection_name = collection.name
                row.operator(
                    'wm.context_set_string',
                    text="",
                    icon='HAND'
                ).value = other_col.name
        
        if parent_count == 0:
            col.label(text="なし", icon='BLANK1')

        layout.separator()

        # コレクション リンク（子コレクション）
        box = layout.box()
        col = box.column()
        col.label(text="コレクション リンク", icon='LINKED')
        
        child_count = len(collection.children)
        
        if child_count > 0:
            for child_col in collection.children:
                row = col.row()
                row.label(text=child_col.name, icon='OUTLINER_COLLECTION')
                # リンク解除ボタン
                row.operator(
                    'collection.unlink_child',
                    text="",
                    icon='UNLINKED'
                ).child_name = child_col.name
        else:
            col.label(text="なし", icon='BLANK1')


class COLLECTION_OT_UnlinkParent(bpy.types.Operator):
    """親コレクションをアンリンク"""
    bl_idname = 'collection.unlink_parent'
    bl_label = 'Unlink Parent Collection'
    
    collection_name: StringProperty()
    
    def execute(self, context):
        # 現在選択中のコレクション
        current_collection = context.collection
        
        # すべてのコレクションをチェック
        for col in bpy.data.collections:
            if col.name == self.collection_name and current_collection in col.children:
                col.children.unlink(current_collection)
                self.report({'INFO'}, f"'{col.name}'から'{current_collection.name}'をアンリンク")
                return {'FINISHED'}
        
        return {'CANCELLED'}


class COLLECTION_OT_UnlinkChild(bpy.types.Operator):
    """子コレクションをアンリンク"""
    bl_idname = 'collection.unlink_child'
    bl_label = 'Unlink Child Collection'
    
    child_name: StringProperty()
    
    def execute(self, context):
        current_collection = context.collection
        
        for child in current_collection.children:
            if child.name == self.child_name:
                current_collection.children.unlink(child)
                self.report({'INFO'}, f"'{current_collection.name}'から'{child.name}'をアンリンク")
                return {'FINISHED'}
        
        return {'CANCELLED'}


def register():
    bpy.utils.register_class(COLLECTION_PT_LinkProperties)
    bpy.utils.register_class(COLLECTION_OT_UnlinkParent)
    bpy.utils.register_class(COLLECTION_OT_UnlinkChild)


def unregister():
    bpy.utils.unregister_class(COLLECTION_PT_LinkProperties)
    bpy.utils.unregister_class(COLLECTION_OT_UnlinkParent)
    bpy.utils.unregister_class(COLLECTION_OT_UnlinkChild)
