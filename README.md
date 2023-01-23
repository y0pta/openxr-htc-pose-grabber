# OpenXR pose grabber for HTC VR headset
### Description
----
Python script allows grabing poses from HTC VR headsets (consisting of helmet and sticks). Although the OpenVR standard is considering to be common for all VR-devices, it still doesn't work properly with some devices, including HTC Vive Pro.
- [OpenXR specs](https://registry.khronos.org/OpenXR/specs/1.0/html/xrspec.html)
- [Python bindings](https://github.com/cmbruns/pyopenxr) <br>
The following script connects to vr equipnment with steamvr and grub pose 3D (helmet, sticks).
#### Requirements
----
- [ ] Install SteamVR;
- [ ] Install [pyopenxr](https://github.com/cmbruns/pyopenxr) through pip;
- [ ] Connect headset to SteamVr and run the script;
- [ ] Enjoy .json with grabbed poses. <br>

> Additional notes for linux users: before running the following script you need to set up the runtime for VR-device.
> The easiest way - use the same profile that steam-VR are already using. So, assign the variable XR_RUNTIME_JSON to steam-generated
> json will help us: 
```
XR_RUNTIME_JSON=~/.steam/steam/steamapps/common/SteamVR/steamxr_linux64.json
```

#### Output format
----
Script produces a .json file with grabbed poses. Each pose consists of:
- positions in VR-space (pre-calibration happens in SteamVR, so you can find an origin there);
- orientations;
- time, when pose was grabbed;

