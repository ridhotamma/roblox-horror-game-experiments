# ClassicHouse roof toggle for Blender: a "House" tab in the 3D viewport sidebar (N) with a button that hides or
# shows the roof group (roof, gables, chimney, attic windows, ceiling and ceiling lights) to look inside.
# Stored in the .blend as a text block with "Register" on, so it comes back when the file is opened
# (Blender asks to allow scripts on load). Running it again replaces the previous registration.
import bpy

ROOF_COLLECTION = "ClassicHouse Roof"


def roof_layer(context):
    def find(lc):
        if lc.collection.name == ROOF_COLLECTION:
            return lc
        for c in lc.children:
            r = find(c)
            if r:
                return r
        return None
    return find(context.view_layer.layer_collection)


class HOUSE_OT_toggle_roof(bpy.types.Operator):
    bl_idname = "house.toggle_roof"
    bl_label = "Toggle Roof"
    bl_description = "Hide or show the roof, ceiling and ceiling lights to look inside the house"

    def execute(self, context):
        lc = roof_layer(context)
        if not lc:
            self.report({'WARNING'}, f"No collection named '{ROOF_COLLECTION}'")
            return {'CANCELLED'}
        lc.hide_viewport = not lc.hide_viewport
        lc.collection.hide_render = lc.hide_viewport
        return {'FINISHED'}


class HOUSE_PT_panel(bpy.types.Panel):
    bl_label = "Classic House"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "House"

    def draw(self, context):
        lc = roof_layer(context)
        col = self.layout.column()
        if not lc:
            col.label(text=f"'{ROOF_COLLECTION}' not found")
            return
        hidden = lc.hide_viewport
        col.operator("house.toggle_roof", text="Show Roof" if hidden else "Hide Roof",
                     icon='HIDE_ON' if hidden else 'HIDE_OFF', depress=hidden)
        col.label(text="Roof hidden: rooms visible" if hidden else "Roof shown")


CLASSES = (HOUSE_OT_toggle_roof, HOUSE_PT_panel)


def register():
    for c in CLASSES:
        try:
            bpy.utils.unregister_class(getattr(bpy.types, c.__name__))
        except Exception:
            pass
        bpy.utils.register_class(c)


if __name__ == "__main__":
    register()
