"""Non-blocking, GPU-first Cycles benchmark for Windows."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import bpy
from bpy.app.handlers import persistent
from .render_benchmark_worker import select_device, candidates

ACTIVE = None
_DEFAULT_CHECKED = False


def configure_windows_default(scene):
    global _DEFAULT_CHECKED
    if _DEFAULT_CHECKED or sys.platform != 'win32' or bpy.app.background or bpy.data.filepath:
        return
    _DEFAULT_CHECKED = True
    from . import prefs
    if not prefs().prefer_render_gpu:
        return
    cycles = bpy.context.preferences.addons['cycles'].preferences
    original = cycles.compute_device_type
    try:
        if original != 'NONE':
            cycles.get_devices()
            if cycles.has_active_device():
                scene.cycles.device = 'GPU'
            return
        profiles = [p for p in candidates() if p['backend'] != 'CPU']
        if profiles:
            select_device(scene, profiles[0])  # OptiX first, CUDA second.
        else:
            cycles.compute_device_type = original
    except (RuntimeError, TypeError):
        cycles.compute_device_type = original



@persistent
def cancel_pending(*_):
    global ACTIVE
    if ACTIVE:
        ACTIVE.cleanup()
        ACTIVE = None


class BLAYA_OT_render_benchmark(bpy.types.Operator):
    bl_idname = 'blaya.render_benchmark'
    bl_label = 'Benchmark & Optimize Cycles'
    bl_description = 'Test NVIDIA GPUs and CPU in a separate process, then apply the fastest working GPU (CPU fallback). Keeps scene quality settings unchanged'

    @classmethod
    def poll(cls, context):
        return sys.platform == 'win32' and not bpy.app.background and ACTIVE is None and not bpy.app.is_job_running('RENDER')

    def cleanup(self):
        global ACTIVE
        process = getattr(self, '_process', None)
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        timer = getattr(self, '_timer', None)
        if timer:
            bpy.context.window_manager.event_timer_remove(timer)
            self._timer = None
        log = getattr(self, '_log', None)
        if log:
            log.close()
        temp = getattr(self, '_temp', None)
        if temp:
            temp.cleanup()
        ACTIVE = None

    def execute(self, context):
        global ACTIVE
        self._scene = context.scene
        self._temp = tempfile.TemporaryDirectory(prefix='kitchen-render-benchmark-')
        directory = Path(self._temp.name)
        self._output = directory / 'result.json'
        self._log = (directory / 'benchmark.log').open('w', encoding='utf-8')
        env = dict(os.environ, BLENDER_USER_CONFIG=str(directory / 'config'))
        try:
            self._process = subprocess.Popen([
                bpy.app.binary_path, '--background', '--factory-startup', '--disable-autoexec',
                '--python-exit-code', '1', '--python',
                str(Path(__file__).with_name('render_benchmark_worker.py')),
                '--', '--output', str(self._output),
            ], stdout=self._log, stderr=subprocess.STDOUT, env=env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self._started = time.monotonic()
            self._timer = context.window_manager.event_timer_add(.5, window=context.window)
            ACTIVE = self
            context.window_manager.blaya_benchmark_status = 'Testing render devices… Escape to cancel'
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        except Exception as error:
            self.cleanup()
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

    def modal(self, context, event):
        if ACTIVE is not self:
            return {'CANCELLED'}
        if event.type == 'ESC' or time.monotonic() - self._started > 600:
            context.window_manager.blaya_benchmark_status = 'Benchmark cancelled or timed out; settings unchanged'
            self.cleanup()
            return {'CANCELLED'}
        if event.type != 'TIMER' or self._process.poll() is None or bpy.app.is_job_running('RENDER'):
            return {'PASS_THROUGH'}
        try:
            if self._process.returncode != 0:
                raise RuntimeError('Benchmark process failed; render settings were not changed')
            report = json.loads(self._output.read_text(encoding='utf-8'))
            best = report['best']
            if best is None:
                raise RuntimeError('No render device completed the benchmark')
            # The captured scene, not whichever scene the user switched to.
            select_device(self._scene, best)
            label = f"{best['name']} / {best['backend']} ({best['seconds']:.2f}s)"
            context.window_manager.blaya_benchmark_status = 'Optimized: ' + label
            context.window_manager.blaya_benchmark_report = json.dumps(report)
            self.report({'INFO'}, 'Cycles configured for ' + label)
        except Exception as error:
            context.window_manager.blaya_benchmark_status = str(error)
            self.report({'ERROR'}, str(error))
            self.cleanup()
            return {'CANCELLED'}
        self.cleanup()
        return {'FINISHED'}

    def cancel(self, context):
        self.cleanup()


def draw(layout, context):
    if sys.platform != 'win32':
        return
    box = layout.box()
    box.label(text='Cycles Performance')
    from . import prefs
    box.prop(prefs(context), 'prefer_render_gpu')
    box.label(text='GPU first · CPU fallback')
    box.operator('blaya.render_benchmark', icon='TIME')
    box.label(text='Tests fixed quality; keeps your samples and resolution.')
    status = context.window_manager.blaya_benchmark_status
    if status:
        box.label(text=status)
    if context.window_manager.blaya_benchmark_report:
        report = json.loads(context.window_manager.blaya_benchmark_report)
        for row in report['results']:
            detail = f"{row['seconds']:.2f}s" if 'seconds' in row else 'Unavailable'
            threads = f" / {row['threads']} threads" if row['backend'] == 'CPU' else ''
            box.label(text=f"{row['name']} / {row['backend']}{threads}: {detail}")
        box.label(text='Save the file and preferences to retain these settings.')
    box.label(text='Small-scene estimate; large scenes may exceed GPU memory.')


def register():
    bpy.utils.register_class(BLAYA_OT_render_benchmark)
    bpy.types.WindowManager.blaya_benchmark_status = bpy.props.StringProperty(options={'SKIP_SAVE'})
    bpy.types.WindowManager.blaya_benchmark_report = bpy.props.StringProperty(options={'SKIP_SAVE'})
    bpy.app.handlers.load_pre.append(cancel_pending)


def unregister():
    cancel_pending()
    bpy.app.handlers.load_pre.remove(cancel_pending)
    del bpy.types.WindowManager.blaya_benchmark_report
    del bpy.types.WindowManager.blaya_benchmark_status
    bpy.utils.unregister_class(BLAYA_OT_render_benchmark)
