"""Verify packaged NVIDIA backends and kernels without requiring a GPU runner."""
from pathlib import Path
import bpy
import _cycles

cuda, optix, *_ = _cycles.get_device_types()
assert cuda and optix, 'Windows build is missing CUDA or OptiX support'
root = Path(bpy.utils.resource_path('LOCAL'))
# The CUDA and OptiX CMake install rules ship zstd-compressed kernels.
kernel_dir = root / 'scripts' / 'addons_core' / 'cycles' / 'lib'
assert list(kernel_dir.glob('kernel_sm_*.cubin.zst')), 'Precompiled CUDA kernels are missing'
assert list(kernel_dir.glob('kernel_optix*.ptx.zst')), 'Precompiled OptiX kernels are missing'
print('PASS: CUDA and OptiX compiled in, with installed GPU kernels (hardware render not tested)')
