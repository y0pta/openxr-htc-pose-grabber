# OpenXR pose grabber for HTC VR headset
### Description
----
Python script allows grabing poses from HTC VR headsets (consisting of helmet and sticks). Although the OpenVR standard is considering to be common for all VR-devices, it still doesn't work properly with some devices, including HTC Vive Pro.
- [OpenXR specs](https://registry.khronos.org/OpenXR/specs/1.0/html/xrspec.html)
- [Python bindings](https://github.com/cmbruns/pyopenxr)
The following script connects to vr equipnment with steamvr and grub pose 3D (helmet, sticks).
#### Requirements
----
1. Install SteamVR;
2. Install [pyopenvr](https://github.com/cmbruns/pyopenxr) through pip;
3. Connect headset to SteamVr and run the script;
4. Enjoy .json with grabbed poses.
#### Output format
----
Script produces a .json file with grabbed poses. Each pose consists of:
- postions in VR-space (pre-calibration happens in SteamVR, so you can find an origin there);
- orientations;
- time, when pose was grabbed;

