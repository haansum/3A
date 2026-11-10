"""Manifest: one short take file + presets -> one fully resolved lock file with a hash.

Reuse layers: characters/ (locked once), arenas/ (once), archetypes/ (validated preset),
takes/ (a few overrides). Each stage's cache key hashes exactly the config it reads, the
upstream stage keys and the source code of that stage, so any stage reruns alone and a
review note is a diff to a take or archetype file, never a hand edit downstream.
"""
import copy
import hashlib
import json
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE_CODE = {
    'character': ['ko/character'],
    'body': ['ko/body'],
    'sim': ['ko/sim'],
    'qa': ['ko/qa'],
    'bake': ['ko/bake'],
    'render': ['ko/render'],
}
QUALITY = {
    'draft': {'engine': 'CYCLES', 'samples': 12, 'res': [640, 360], 'fps': 30,
              'motion_blur': False, 'dof': False, 'shots': ['live', 'tight'],
              'frame_step': 2, 'max_subdiv': 1},     # 15 fps, real-time playback
    'full': {'engine': 'CYCLES', 'samples': 192, 'res': [1920, 1080], 'fps': 30,
             'motion_blur': True, 'dof': True,
             'shots': ['live', 'referee', 'opponent', 'orbit', 'tight'],
             'frame_step': 1, 'max_subdiv': None},
}


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) \
            else copy.deepcopy(v)
    return out


def _yaml(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return yaml.safe_load(f) or {}


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def code_hash(stage):
    h = hashlib.sha256()
    for d in STAGE_CODE[stage]:
        for base, _, files in sorted(os.walk(os.path.join(ROOT, d))):
            for f in sorted(files):
                if f.endswith('.py'):
                    h.update(open(os.path.join(base, f), 'rb').read())
    return h.hexdigest()[:16]


def resolve(take_path, quality=None):
    take = yaml.safe_load(open(take_path))
    char = _yaml('presets', 'characters', take['character'] + '.yaml')
    arena = _yaml('presets', 'arenas', take['arena'] + '.yaml')
    arch = _yaml('presets', 'archetypes', take['archetype'] + '.yaml')
    cfg = deep_merge(arch, take.get('overrides'))
    cfg['arena'] = deep_merge(arena, (take.get('overrides') or {}).get('arena'))
    cfg['arena']['rope_y'] = -float(cfg['arena']['rope_distance'])
    cfg['sim']['seed'] = take.get('seed', 0)
    q = quality or take.get('quality', 'draft')
    lock = {'take': os.path.splitext(os.path.basename(take_path))[0],
            'character': char, 'quality': q, 'render': QUALITY[q], **cfg}
    src = os.path.join(ROOT, char['source']['file'])
    if os.path.exists(src):
        lock['character']['source']['sha256'] = hashlib.sha256(open(src, 'rb').read()).hexdigest()
    k = {}
    k['character'] = sha([lock['character']['source'], lock['character'].get('bone_map'),
                          lock['character'].get('outfit'),
                          code_hash('character')])[:12]
    k['body'] = sha([k['character'], lock['character']['mass'], code_hash('body')])[:12]
    k['sim'] = sha([k['body'], lock['arena'], lock['sim'], lock['motion'], lock.get('strike'),
                    lock['controller'], code_hash('sim')])[:12]
    k['qa'] = sha([k['sim'], lock.get('outcome'), code_hash('qa')])[:12]
    k['bake'] = sha([k['sim'], k['character'], code_hash('bake')])[:12]
    k['render'] = sha([k['bake'], lock['arena'], lock['render'], code_hash('render')])[:12]
    lock['keys'] = k
    lock['hash'] = sha(lock)[:12]
    return lock


def stage_dir(lock, stage):
    return os.path.join(ROOT, 'build', stage, lock['keys'][stage])
