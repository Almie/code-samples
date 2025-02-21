import bpy
from mathutils import Vector


def calculateViewTarget(armature):
    # Replace these with the appropriate names for armature and eye bones.
    eye_bone_L = "eye_left"
    eye_bone_R = "eye_right"
    view_target_name = "viewTarget"


    def look_at(obj, target, roll=0):
        direction = target - obj
        quat = direction.to_track_quat('-Y', 'Z')
        quat = quat.to_matrix().to_4x4()
        quat.translation = obj
        return quat


    # Get the armature object, eye bones, and view target object.
    eye_bone_L = armature.pose.bones.get(eye_bone_L)
    eye_bone_R = armature.pose.bones.get(eye_bone_R)
    view_target = bpy.data.objects.get(view_target_name)



    frame_start = bpy.context.scene.frame_start
    frame_end = bpy.context.scene.frame_end

    for frame_index in range(frame_start, frame_end):
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

