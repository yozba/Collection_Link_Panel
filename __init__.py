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
from bpy.types import Panel

class COLLECTION_PT_LinkProperties(Panel):
    """Collection Link Panel"""
    bl_label = "Collection Link Panel"
    bl_idname = "COLLECTION_PT_link_properties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context):
        pass

class COLLECTION_PT_CollectionLinking(Panel):
    """Collection Linking"""
    bl_label = "Linking to"
    bl_idname = "COLLECTION_PT_collection_linking"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"
    bl_parent_id = "COLLECTION_PT_link_properties"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        collection = context.collection
        
        col = layout.column()
        parent_count = 0
        for other_col in bpy.data.collections:
            if collection in other_col.children.values():
                parent_count += 1
                col.label(text=other_col.name, icon='OUTLINER_COLLECTION')

        if parent_count == 0:
            col.label(text="None")

class COLLECTION_PT_CollectionLinked(Panel):
    """Collection Linked"""
    bl_label = "Linked from"
    bl_idname = "COLLECTION_PT_collection_linked"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"
    bl_parent_id = "COLLECTION_PT_link_properties"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        collection = context.collection
        
        col = layout.column()
        child_count = len(collection.children)
        
        if child_count > 0:
            for child_col in collection.children:
                row = col.row()
                row.label(text=child_col.name, icon='OUTLINER_COLLECTION')
        else:
            col.label(text="None")


def register():
    bpy.utils.register_class(COLLECTION_PT_LinkProperties)
    bpy.utils.register_class(COLLECTION_PT_CollectionLinking)
    bpy.utils.register_class(COLLECTION_PT_CollectionLinked)


def unregister():
    bpy.utils.unregister_class(COLLECTION_PT_LinkProperties)
    bpy.utils.unregister_class(COLLECTION_PT_CollectionLinking)
    bpy.utils.unregister_class(COLLECTION_PT_CollectionLinked)
