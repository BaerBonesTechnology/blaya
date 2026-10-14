"""Check that sccache reuses both CUDA cubin and OptiX-style PTX compilations."""
import json
from pathlib import Path
import subprocess
import tempfile


def hits():
    stats = json.loads(subprocess.check_output(
        ['sccache', '--show-stats', '--stats-format', 'json'], text=True))
    return sum(stats['stats']['cache_hits']['counts'].values())


with tempfile.TemporaryDirectory(prefix='kitchen-cuda-cache-') as directory:
    root = Path(directory)
    source = root / 'probe.cu'
    source.write_text('extern "C" __global__ void probe(float *p) { p[threadIdx.x] += 1.0f; }\n')
    for output_format in ('cubin', 'ptx'):
        output = root / f'probe.{output_format}'
        command = ['sccache', 'nvcc', f'--{output_format}', '-arch=sm_75',
                   '-D_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH', str(source), '-o', str(output)]
        subprocess.run(command, check=True)
        expected = output.read_bytes()
        before = hits()
        output.unlink()
        subprocess.run(command, check=True)
        assert hits() > before, f'{output_format} compilation did not produce a cache hit'
        assert output.read_bytes() == expected, f'{output_format} cache changed the output'
        print(f'PASS: {output_format} restored from compiler cache')
