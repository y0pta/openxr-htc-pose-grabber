import xr
import attrdict
import logging
import time
from ctypes import byref, POINTER, c_void_p, cast, pointer, c_int32
from xr import KHR_OPENGL_ENABLE_EXTENSION_NAME, EXT_HAND_TRACKING_EXTENSION_NAME, HTC_VIVE_COSMOS_CONTROLLER_INTERACTION_EXTENSION_NAME

# Necessary extensions for vive
EXT_NEEDED = [KHR_OPENGL_ENABLE_EXTENSION_NAME,
                EXT_HAND_TRACKING_EXTENSION_NAME,
                HTC_VIVE_COSMOS_CONTROLLER_INTERACTION_EXTENSION_NAME]

INTERACTION_PROFILE = "/interaction_profiles/htc/vive_controller"

HAND_PATH_STR = attrdict.AttrDict({"RIGHT": "/user/hand/right",
                              "LEFT": "/user/hand/left"})

POSE_PATH_STR = attrdict.AttrDict({"RIGHT": "/user/hand/right/input/aim/pose",
                              "LEFT": "/user/hand/left/input/aim/pose"})

LOG_FILENAME = "xr_log.txt"
logging.basicConfig(filename=LOG_FILENAME, level=logging.INFO, filemode="w")
logger = logging.getLogger("vive.reader")

def handle_key(handle):
    return hex(cast(handle, c_void_p).value)

class VivePose:
    def __init__(self,
                 t=0,
                 rhand=xr.Posef(),
                 lhand=xr.Posef(),
                 head=xr.Posef()):
        self.time = t
        self.right_hand = rhand
        self.left_hand = lhand
        self.head = head #Left eye position


    def add_via_path(self, path, value):
        if 'left' in path.lower():
            self.left_hand = value
        elif 'right' in path.lower():
            self.right_hand = value

    def is_valid(self):
        if self.time == 0:
            return False

        b = (self.right_hand.position is None)
        c = (self.left_hand.position is None)
        d = (self.head.position is None)
        return b+c+d > 0

    def json_dict(self):

        dict = {"time": self.time,
                "right_hand": {"position": self.right_hand.position.as_numpy().tolist(),
                               "orientation": self.right_hand.orientation.as_numpy().tolist()},
                "left_hand": {"position": self.left_hand.position.as_numpy().tolist(),
                               "orientation": self.left_hand.orientation.as_numpy().tolist()},
                "head": {"position": self.head.position.as_numpy().tolist(),
                               "orientation": self.head.orientation.as_numpy().tolist()}
                }
        return dict



class VivePoseReader(xr.ContextObject):
    def __init__(self):
        available_ext = xr.enumerate_instance_extension_properties()
        for ext in EXT_NEEDED:
            if not ext in available_ext:
                text = "HTC VIVE is unsupported in this version of OpenXR"
                logger.error(text)
                raise RuntimeError(text)
        instance_create_info = xr.InstanceCreateInfo(enabled_extension_names=EXT_NEEDED)
        super().__init__(instance_create_info=instance_create_info)

        # Context: all staff responsible for Instance, Session, Graphics, Swapchains
        self.context = super()
        # Interaction profile
        self.interaction_profile_path = INTERACTION_PROFILE
        # Left and right hand paths
        self.hand_paths = attrdict.AttrDict({})
        # Left and right pose paths
        self.hand_pose_paths = attrdict.AttrDict({})
        # Here will be xr.Action associated with retrieving poses
        self.hand_pose_action = None
        # Action spaces for each hand
        self.action_spaces = attrdict.AttrDict({})
        # Initial space, extracting poses from the world origin
        self.world_space = None
        # Will not create own action set, use default action set instead
        # self.action_set = None
        # First time recieved from runtime
        self.initial_time = 0

    def __enter__(self):
        logger.info("Initializing XR Instance...")
        super().__enter__()
        self.init_pose_actions()

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info("Deleting XR Instance...")
        super(VivePoseReader, self).__exit__(exc_type, exc_val, exc_tb)

    def init_pose_actions(self):
        """
        Common way to act with runtime input
           1. Create action set (we use default actionset instead)
           2. Create XrPathes for each hand, interaction profile, poses paths to access the runtime
           3. Create action for hand pose (2 subaction path for each hand)
           4. Get suggest interaction profile from runtime
           5. Create Action space (in which coordinate system pose will be counted)
           6. Attach action set to session
        """
        assert self.instance is not None
        # create hand paths to access the runtime
        self.hand_paths = attrdict.AttrDict({
            'LEFT': xr.string_to_path(self.instance, HAND_PATH_STR.LEFT),
            'RIGHT': xr.string_to_path(self.instance, HAND_PATH_STR.RIGHT),
        })
        # create paths to access poses
        self.hand_pose_paths = attrdict.AttrDict({
            'LEFT': xr.string_to_path(self.instance, POSE_PATH_STR.LEFT),
            'RIGHT': xr.string_to_path(self.instance, POSE_PATH_STR.RIGHT),
        })
        # create interaction profile path
        self.interaction_profile_path = xr.string_to_path(self.instance, INTERACTION_PROFILE)

        # Create action
        self.hand_pose_action = xr.create_action(
            action_set=self.default_action_set,
            create_info=xr.ActionCreateInfo(
                action_type=xr.ActionType.POSE_INPUT,
                action_name="hand_pose",
                localized_action_name="Hand Pose",
                count_subaction_paths=len(self.hand_paths),
                subaction_paths=self.hand_paths.values(),
            ),
        )
        suggested_bindings = (xr.ActionSuggestedBinding * 2)(
            xr.ActionSuggestedBinding(
                action=self.hand_pose_action,
                binding=self.hand_pose_paths.LEFT,
            ),
            xr.ActionSuggestedBinding(
                action=self.hand_pose_action,
                binding=self.hand_pose_paths.RIGHT,
            ),
        )
        xr.suggest_interaction_profile_bindings(
            instance=self.instance,
            suggested_bindings=xr.InteractionProfileSuggestedBinding(
                interaction_profile=self.interaction_profile_path,
                count_suggested_bindings=len(suggested_bindings),
                suggested_bindings=suggested_bindings,
            ),
        )

        self.action_spaces = attrdict.AttrDict({
            'LEFT': xr.create_action_space(
                session=self.session,
                create_info=xr.ActionSpaceCreateInfo(
                    action=self.hand_pose_action,
                    subaction_path=self.hand_paths.LEFT,
                ),
            ),
            'RIGHT': xr.create_action_space(
                session=self.session,
                create_info=xr.ActionSpaceCreateInfo(
                    action=self.hand_pose_action,
                    subaction_path=self.hand_paths.RIGHT,
                ),
            ),
        })
        world_space_info = xr.ReferenceSpaceCreateInfo(
            reference_space_type=xr.ReferenceSpaceType.STAGE,
            pose_in_reference_space=xr.Posef(),
        )
        self.world_space = xr.create_reference_space(
            session=self.session,
            create_info=world_space_info,
        )
        xr.attach_session_action_sets(
            session=self.session,
            attach_info=xr.SessionActionSetsAttachInfo(
                count_action_sets=len(self.action_sets),
                action_sets=(xr.ActionSet * len(self.action_sets))(
                    *self.action_sets
                )
            ),
        )

    def get_pose(self, path, space, rtime):
        if rtime > self.initial_time:
            space_location = xr.locate_space(space=space,
                                             base_space=self.world_space,
                                             time=rtime)
            loc_flags = space_location.location_flags
            if loc_flags & xr.SPACE_LOCATION_POSITION_VALID_BIT == 0:
                logger.warning(f"time={rtime / 1000000000}\n"
                               f"Invalid time called for locate_space or runtime doesn't know how" 
                               f"to locate spaces for {xr.path_to_string(self.instance, path)}")

            if loc_flags & xr.SPACE_LOCATION_POSITION_TRACKED_BIT == 0:
                logger.warning(f"Position disoriented, tracking lost for {xr.path_to_string(self.instance, path)}")

            if (loc_flags & xr.SPACE_LOCATION_POSITION_VALID_BIT != 0
                    and loc_flags & xr.SPACE_LOCATION_ORIENTATION_VALID_BIT != 0):
                logger.info(f"-------------------------------------- \n"
                            f"Time={rtime / 1000000000} \n"
                            f"{xr.path_to_string(self.instance, path)} \n"
                            f"Pose={space_location.pose} \n" 
                            f"-------------------------------------- \n")

            return space_location.pose
        else:
            logger.warning(f"Attemp to ask pose for invalid time={rtime}")
            return xr.SpaceLocation().pose

    def poll_actions(self, get_time=0):
        assert self.session is not None
        if self.session_state == xr.SessionState.FOCUSED:
            # Try to receive values for all paths
            active_action_set = xr.ActiveActionSet(
                action_set=self.default_action_set,
                subaction_path=xr.NULL_PATH,
            )
            xr.sync_actions(
                session=self.session,
                sync_info=xr.ActionsSyncInfo(
                    count_active_action_sets=1,
                    active_action_sets=pointer(active_action_set),
                ),
            )

            vive_pose = VivePose()
            vive_pose.time = get_time
            for hand, path in self.hand_paths.items():
                get_info = xr.ActionStateGetInfo(
                    action=self.hand_pose_action,
                    subaction_path=path,
                )
                value = xr.get_action_state_pose(self.session, get_info)
                pose = self.get_pose(path, self.action_spaces[hand], get_time)
                vive_pose.add_via_path(hand, pose)

            return vive_pose

        else:
            return VivePose()

    def poll_events(self):
        """Process any events in the event queue."""
        self.exit_render_loop = False
        self.request_restart = False
        # Process all pending messages.
        while True:
            event = self.try_read_next_event()
            if event is None:
                break
            event_type = event.type

            if event_type == xr.StructureType.EVENT_DATA_INSTANCE_LOSS_PENDING:
                logger.info("EVENT: Session lost pending")
                self.exit_render_loop = True
                self.request_restart = True
                return
            elif event_type == xr.StructureType.EVENT_DATA_SESSION_STATE_CHANGED:
                logger.info("EVENT: Session change state")
                self.session_state_changed_event(event)
            elif event_type == xr.StructureType.EVENT_DATA_INTERACTION_PROFILE_CHANGED:
                new_profile = self.get_interaction_profile()
                try:
                    logger.warning(f"EVENT: Interaction profile changed to "
                                    f"{xr.path_to_string(self.instance, new_profile)}")
                    self.interaction_profile_path = new_profile
                except:
                    logger.warning(f"EVENT: Interaction profile changed to NULL")
                    #self.interaction_profile_path = xr.NULL_PATH

            elif event_type == xr.StructureType.EVENT_DATA_REFERENCE_SPACE_CHANGE_PENDING:
                logger.warning("EVENT: Space change pending")
            else:
                logger.warning("EVENT: Unknown event")

    def session_state_changed_event(self, event_state):
        assert self.session is not None
        event = cast(byref(event_state), POINTER(xr.EventDataSessionStateChanged)).contents
        old_state = self.session_state
        self.session_state = xr.SessionState(event.state)
        key = cast(self.session, c_void_p).value

        logger.info(f"Session changed from {xr.SessionState(old_state)} to {xr.SessionState(self.session_state)}")
        if event.session is not None and handle_key(event.session) != handle_key(self.session):
            logger.info(f"XrEventDataSessionStateChanged for unknown session {event.session}\n"
                        f"       Current session {self.session}")
            self.exit_render_loop = True
            self.request_restart = True

        if self.session_state == xr.SessionState.READY:
            assert self.session is not None
            xr.begin_session(
                session=self.session,
                begin_info=xr.SessionBeginInfo(
                    primary_view_configuration_type=xr.ViewConfigurationType.PRIMARY_STEREO,
                ),
            )
            self.session_is_running = True
            logger.info(f"Session started.")

        elif self.session_state == xr.SessionState.STOPPING:
            assert self.session is not None
            self.session_running = False
            xr.end_session(self.session)
            logger.info(f"Session ended.")

        elif self.session_state == xr.SessionState.EXITING:
            self.exit_render_loop = True
            # Do not attempt to restart because user closed this session.
            self.request_restart = False
            logger.info(f"Session exited.")

        elif self.session_state == xr.SessionState.LOSS_PENDING:
            logger.warning("Session lost pending. Exit")
            self.exit_render_loop = True
            # Poll for a new instance.
            self.request_restart = True

        elif self.session_state == xr.SessionState.FOCUSED:
            logger.info("Session focused. Ready to input.")

        elif self.session_state == xr.SessionState.SYNCHRONIZED:
            logger.info("Session synchronized.")

        elif self.session_state == xr.SessionState.VISIBLE:
            logger.info("Session visible.")

    def try_read_next_event(self):
        assert self.session is not None
        #  It is sufficient to clear the just the XrEventDataBuffer header to
        #  XR_TYPE_EVENT_DATA_BUFFER
        base_header = xr.EventDataBuffer()
        base_header.type = xr.StructureType.EVENT_DATA_BUFFER
        result = xr.raw_functions.xrPollEvent(self.instance, byref(base_header))
        if result == xr.Result.SUCCESS:
            if base_header.type == xr.StructureType.EVENT_DATA_EVENTS_LOST:
                events_lost = cast(base_header, POINTER(xr.EventDataEventsLost))
                logger.warning(f"EVENT LOST: {events_lost}")
            return base_header
        if result == xr.Result.EVENT_UNAVAILABLE:
            return None
        result2 = xr.check_result(result)
        raise result2

    def get_interaction_profile(self):
        profile_state = xr.get_current_interaction_profile(self.session, self.hand_paths.RIGHT)
        new_profile = profile_state.interaction_profile
        return new_profile

    def render_frame(self):
        frame_state = xr.wait_frame(self.session)
        logger.info(f"Current frame display time: {frame_state.predicted_display_time / 1000000000}")

        view_state, views = xr.locate_views(
                session=self.session,
                view_locate_info=xr.ViewLocateInfo(
                    view_configuration_type=self.view_configuration_type,
                    display_time=frame_state.predicted_display_time,
                    space=self.space,
                )
            )

        xr.begin_frame(self.session)

        self.render_layers = []
        self.graphics.make_current()
        from OpenGL import GL

        GL.glClearColor(1.0, 0.5, 0.5, 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        xr.end_frame(
            self.session,
            frame_end_info=xr.FrameEndInfo(
                display_time=frame_state.predicted_display_time,
                environment_blend_mode=self.environment_blend_mode,
                layers=self.render_layers,
            )
        )
        return frame_state, views[xr.Eye.LEFT.value].pose

    def run(self):
        t = 0
        i = 0
        # Loop over the render frames
        while True:
            # 1. Poll events (xr.poll_event)
            # 2. Sync actions (xr.sync_actions)
            # 3. Render frame (xr.wait_frame, xr.begin_frame, xr.end_frame)
            if self.graphics.poll_events() or self.exit_render_loop:
                break

            self.poll_events()
            if self.session_is_running:
                # TODO: try to change places
                vive_pose = self.poll_actions(t)
                frame_state, vive_pose.head = self.render_frame()
                new_time = frame_state.predicted_display_time
                if t == 0:
                    self.initial_time = new_time

                t = new_time
                yield vive_pose
