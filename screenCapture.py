import dxcam

print(dxcam.device_info())
print(dxcam.output_info())

camera = dxcam.create()

left, top = (1920 - 640) // 2, (1080 - 640) // 2
right, bottom = left + 640, top + 640
region = (left, top, right, bottom)

frame = camera.grab(region=region)  # numpy.ndarray of size (640x640x3) -> (HXWXC)