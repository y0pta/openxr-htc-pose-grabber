"""
VivePoseReader - openxr program for capturing controllers positions.
"""
import vive_pose_reader
from vive_pose_reader import VivePoseReader
import sys, threading, time, os

start_event = threading.Event()
stop_event = threading.Event()

def poll_keyboard():
    print("Press ENTER key to start, q to stop")
    while True:
        input = sys.stdin.read(1)
        if input == '\n' and not start_event.is_set():
            start_event.set()
            print('Program started capturing.')

        if input.rstrip() == 'q' and not stop_event.is_set():
            stop_event.set()
            print('Capturing stopped. Exiting.')

def save_poses_json(poses, path):
    import json
    # convert each pose to json dictionary
    poses_ = []
    for pose in poses:
        poses_.append(pose.json_dict())

    with open(path, 'w') as f:
        f.write(json.dumps(poses_, indent=4))


JSON_WRITE_PATH = "poses.json"
# approximate frame per second
FRAME_RATE = 4


if __name__ == "__main__":
    # Poll keyboard for start and stop in separate thread
    threading.Thread(target=poll_keyboard, daemon=True).start()

    poses = []
    reader = VivePoseReader()
    initial_time = 0
    # Init reader
    with reader:
        # Run frame loop
        for i, pose in enumerate(reader.run()):
            # Wait for start data capturing event(hardware init claims come time)
            if not start_event.is_set():
                time.sleep(0.25)
                continue

            # Catch keyboard interruption
            if stop_event.is_set():
                initial_time = reader.initial_time
                reader.exit_render_loop = True

            # Record only valid poses
            if pose.is_valid():
                # Each pose consists of:
                # - time - internal hardware time, when pose was captured
                # - left hand position and orientation
                # - right hand position and orientation
                # - head position and orientation (left eye)
                # in world coordinate system
                poses.append(pose)

            # Frame period could be specified here
            time.sleep(1.0/FRAME_RATE)

    print(f"Totally {len(poses)} frames recorded.\n"
          f"Initial time: {initial_time}.\n"
          f"Stop time: {poses[len(poses)-1].time}.\n"
          f"Log: {os.path.dirname(__file__)}\{vive_pose_reader.LOG_FILENAME}\n"
          f"Poses.json will be save in {os.path.dirname(__file__)}\{JSON_WRITE_PATH}\n")

    save_poses_json(poses, JSON_WRITE_PATH)
