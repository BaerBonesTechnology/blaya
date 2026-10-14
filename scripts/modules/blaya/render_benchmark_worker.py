"""Disposable render benchmark, launched by render_benchmark in a separate app."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

import bpy
from mathutils import Vector


def candidates():
    prefs = bpy.context.preferences.addons['cycles'].preferences
    result = []
    # Test each NVIDIA device through both supported paths.
    for backend in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
            for device in prefs.devices:
                if device.type == backend and getattr(device, 'meets_driver_requirement', True):
                    result.append(dict(backend=backend, id=device.id, name=device.name, threads=0))
        except (TypeError, RuntimeError):
            continue
    cores = min(os.cpu_count() or 1, 1024)
    for count in sorted({max(1, cores // 2), cores}, reverse=True):
        result.append(dict(backend='CPU', id='CPU', name='CPU', threads=count))
    return result


def select_device(scene, profile):
    prefs = bpy.context.preferences.addons['cycles'].preferences
    if profile['backend'] == 'CPU':
        scene.cycles.device = 'CPU'
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = profile['threads']
    else:
        original = prefs.compute_device_type
        enabled = {device.id: device.use for device in prefs.devices}
        try:
            prefs.compute_device_type = profile['backend']
            prefs.get_devices()
            available = [d for d in prefs.devices if d.type == profile['backend'] and d.id == profile['id']]
            if not available:
                raise RuntimeError('Benchmarked GPU is no longer available')
            # Check the target scene is still valid before changing device preferences.
            scene.cycles.device = 'GPU'
            scene.render.threads_mode = 'AUTO'
            for device in prefs.devices:
                device.use = device in available
        except Exception:
            prefs.compute_device_type = original
            for device in prefs.devices:
                if device.id in enabled:
                    device.use = enabled[device.id]
            raise


def choose(results):
    valid = [r for r in results if 'seconds' in r and r['seconds'] > 0]
    gpu = [r for r in valid if r['backend'] != 'CPU']
    # GPU first; CPU is a fallback when every GPU path fails or none exists.
    return min(gpu or valid, key=lambda r: r['seconds']) if valid else None


def make_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 32
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False
    scene.cycles.seed = 17
    bpy.ops.mesh.primitive_plane_add(size=20)
    for x, roughness in ((-1.3, .15), (1.3, .65)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=(x, 0, 1))
        obj = bpy.context.object
        material = bpy.data.materials.new('Benchmark')
        material.use_nodes = True
        shader = material.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Roughness'].default_value = roughness
        shader.inputs['Metallic'].default_value = .6
        obj.data.materials.append(material)
    bpy.ops.object.light_add(type='AREA', location=(1, -3, 6))
    bpy.context.object.data.energy = 1200
    bpy.context.object.data.size = 4
    bpy.ops.object.camera_add(location=(6, -9, 5))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, .7)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = camera
    return scene


def main(output):
    scene = make_scene()
    results = []
    for profile in candidates():
        try:
            select_device(scene, profile)
            bpy.ops.render.render()  # Warm up kernels before timing.
            times = []
            for _ in range(2):
                start = time.perf_counter()
                bpy.ops.render.render()
                times.append(time.perf_counter() - start)
            results.append(dict(profile, seconds=statistics.median(times)))
        except Exception as error:
            results.append(dict(profile, error=str(error)))
    report = dict(schema=1, results=results, best=choose(results),
                  version=list(bpy.app.version), logical_cpus=os.cpu_count())
    Path(output).write_text(json.dumps(report), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    main(args.output)
