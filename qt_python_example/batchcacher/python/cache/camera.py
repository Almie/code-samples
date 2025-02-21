import bpy
import sys
import os

def main():
    anim_path = sys.argv[sys.argv.index("anim-path")+1]
    export_path = sys.argv[sys.argv.index("export-path")+1]
    startFrame = int(sys.argv[sys.argv.index("--frame-start")+1])
    endFrame = int(sys.argv[sys.argv.index("--frame-end")+1])
    shotName = sys.argv[sys.argv.index("shot-name")+1]
    debug = "--debug" in sys.argv

    #delete all objects for empty scene
    for obj in bpy.context.scene.objects:
        obj.select_set(True)
    bpy.ops.object.delete()


    #override context to allow euler filtering
    """
    override = bpy.context.copy()
    window = bpy.context.window_manager.windows[0]
    screen = window.screen
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'WINDOW':
                    override['area'] = area
                    override['screen'] = screen
                    override['region'] = region
                    override['scene'] = bpy.context.scene
                    override['window'] = bpy.context.window
    """

    #import camera animation
    bpy.ops.import_scene.smd(filepath=anim_path)

    #bake animation
    bpy.ops.nla.bake(frame_start=0, frame_end=endFrame, step=1, only_selected=False, use_current_action=False, bake_types={'POSE', 'OBJECT'})

    #rename camera object
    bpy.context.selected_objects[0].name = "{}_camera".format(shotName)

    #remove unbaked actions
    bakedAction = bpy.context.selected_objects[0].animation_data.action
    for action in bpy.data.actions:
        if action == bakedAction:
            continue
        bpy.data.actions.remove(action)

    #create necessary directories
    if not os.path.isdir(os.path.dirname(export_path)):
        os.makedirs(os.path.dirname(export_path))

    bpy.context.scene.frame_start = startFrame
    bpy.context.scene.frame_end = endFrame
    bpy.ops.export_scene.fbx(filepath=export_path, object_types={'CAMERA'},
                            use_selection=True, global_scale=0.0254, bake_anim=True,
                            bake_anim_use_all_bones=True,
                            bake_anim_use_nla_strips=True,
                            bake_anim_use_all_actions=True,
                            bake_anim_force_startend_keying=False,
                            bake_anim_step=1, bake_anim_simplify_factor=0)

    if debug:
        debugPath = sys.argv[sys.argv.index("--debug")+1]

        if not os.path.isdir(os.path.dirname(debugPath)):
            os.makedirs(os.path.dirname(debugPath))

        bpy.ops.wm.save_as_mainfile(filepath=debugPath)

if __name__ == "__main__":
    main()
