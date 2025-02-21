import bpy
import sys
import os
import json
from mathutils import Vector

def onFrameChange(scene):
    cachedFrames = scene.frame_current-scene.frame_start
    totalFrames = scene.frame_end-scene.frame_start
    print('Caching Animation|{}|{}'.format(cachedFrames, totalFrames))
    sys.stdout.flush()

def calculateViewTarget(armature):
    print("CALCULATE VIEW TARGET START")
    # Replace these with the appropriate names for armature and eye bones.
    eye_bone_name_L = "eye_left"
    eye_bone_name_R = "eye_right"
    view_target_name = "viewTarget"


    def look_at(obj, target, roll=0):
        direction = target - obj
        quat = direction.to_track_quat('Y', 'Z')
        quat = quat.to_matrix().to_4x4()
        quat.translation = obj
        return quat

    print("CALCULATE VIEW TARGET 0")


    # Get the armature object, eye bones, and view target object.
    eye_bone_L = armature.pose.bones.get(eye_bone_name_L)
    eye_bone_R = armature.pose.bones.get(eye_bone_name_R)
    armature.driver_remove('pose.bones["{}"].rotation_euler'.format(eye_bone_name_L))
    armature.driver_remove('pose.bones["{}"].rotation_euler'.format(eye_bone_name_R))
    view_target = bpy.data.objects.get(view_target_name)

    print("CALCULATE VIEW TARGET 1")



    frame_start = bpy.context.scene.frame_start
    frame_end = bpy.context.scene.frame_end

    

    print("CALCULATE VIEW TARGET 2", frame_start, frame_end)

    for frame_index in range(frame_start, frame_end):
        print("CALCULATE VIEW TARGET FRAME", frame_index)
        bpy.context.scene.frame_set(frame_index)
        

        if armature and eye_bone_L and eye_bone_R and view_target:
            for eye_bone in [eye_bone_L, eye_bone_R]:
                # Get eye bone and view target positions in world coordinates.
                eye_bone_pos = armature.matrix_world @ eye_bone.head
                view_target_pos = view_target.matrix_world.translation

                # Calculate and set the rotation matrix.
                look_matrix = look_at(eye_bone_pos, view_target_pos)
                eye_bone.matrix = armature.matrix_world.inverted() @ look_matrix
                
                # Set keyframe on eye bone.
                eye_bone.keyframe_insert('rotation_euler', frame=frame_index)

            print("Eye bones' rotation updated to look at the view target.")
        else:
            print("Failed to find the specified armature, eye bones, or view target.")



def main():
    anim_path = sys.argv[sys.argv.index("anim-path")+1]
    export_path = sys.argv[sys.argv.index("export-path")+1]
    startFrame = int(sys.argv[sys.argv.index("--frame-start")+1])
    endFrame = int(sys.argv[sys.argv.index("--frame-end")+1])
    debug = "--debug" in sys.argv
    transforms = "--transforms" in sys.argv

    #import animation dmx
    bpy.ops.import_scene.smd(filepath=anim_path)

    bpy.context.scene.frame_start = startFrame
    bpy.context.scene.frame_end = endFrame

    #find the armature
    armature = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            armature = obj
            break

    #calculate eye rotation from viewTarget
    print('ARMATURE FOUND:', armature)
    if armature:
        calculateViewTarget(armature)

    #make directories for cache output
    if not os.path.isdir(os.path.dirname(export_path)):
        os.makedirs(os.path.dirname(export_path))

    #create event handler for progress report
    bpy.app.handlers.frame_change_post.append(onFrameChange)

    #select meshes only
    for obj in bpy.context.scene.objects:
        obj.select_set(obj.type == 'MESH')

    bpy.ops.wm.alembic_export('INVOKE_DEFAULT', filepath=export_path, start=startFrame, end=endFrame, selected=True, flatten=True, uvs=True, normals=True, face_sets=True, global_scale=0.0254)

    #bake and export transforms
    if transforms:
        transformsPath = sys.argv[sys.argv.index("--transforms")+1]
        transformsListPath = os.path.join(os.path.dirname(transformsPath), '.'.join(list(os.path.splitext(os.path.basename(transformsPath))[:-1])+["json"]))

        if not os.path.isdir(os.path.dirname(transformsPath)):
            os.makedirs(os.path.dirname(transformsPath))

        for obj in bpy.context.scene.objects:
            obj.select_set(obj.type == 'EMPTY')
        if len(bpy.context.selected_objects) > 0:
            transform_names = [obj.name for obj in bpy.context.selected_objects]
            bpy.ops.nla.bake(frame_start=startFrame, frame_end=endFrame, step=1, only_selected=True, use_current_action=False, visual_keying=True, clear_constraints=True, clean_curves=False, bake_types={'OBJECT'})
            bpy.ops.export_scene.fbx(filepath=transformsPath, object_types={'EMPTY'},
                                    use_selection=True, global_scale=0.0254, bake_anim=True,
                                    bake_anim_use_all_bones=True,
                                    bake_anim_use_nla_strips=False,
                                    bake_anim_use_all_actions=False,
                                    bake_anim_force_startend_keying=False,
                                    bake_anim_step=1, bake_anim_simplify_factor=0)
        with open(transformsListPath, 'w') as f:
            json.dump(transform_names, f)

    if debug:
        debugPath = sys.argv[sys.argv.index("--debug")+1]

        if not os.path.isdir(os.path.dirname(debugPath)):
            os.makedirs(os.path.dirname(debugPath))

        bpy.ops.wm.save_as_mainfile(filepath=debugPath)

if __name__ == "__main__":
    main()
