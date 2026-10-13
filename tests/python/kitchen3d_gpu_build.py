"""Verify packaged NVIDIA backends and kernels without requiring a GPU runner."""
from pathlib import Path
import bpy
import _cycles

cuda, optix, *_ = _cycles.get_device_types()
assert cuda and optix, 'Windows build is missing CUDA or OptiX support'
root = Path(bpy.utils.resource_path('LOCAL'))
assert list(root.rglob('kernel_sm_*.cubin')), 'Precompiled CUDA kernels are missing'
assert list(root.rglob('kernel_optix*.ptx')), 'Precompiled OptiX kernels are missing'
print('PASS: CUDA and OptiX compiled in, with installed GPU kernels (hardware render not tested)')
