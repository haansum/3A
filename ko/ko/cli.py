"""ko build <take.yaml> [--quality draft|full] [--to STAGE] [--force STAGE]

Stages: character -> body -> sim -> qa -> bake -> render. Outputs live in
build/<stage>/<key>/ where key hashes everything the stage reads; an existing directory with
a DONE marker is a cache hit. A failing QA gate stops the chain before any Blender work.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

from . import manifest

STAGES = ['character', 'body', 'sim', 'qa', 'bake', 'render']


def done(d):
    return os.path.exists(os.path.join(d, 'DONE'))


def mark(d, lock):
    json.dump(lock, open(os.path.join(d, 'take.lock.json'), 'w'), indent=1)
    open(os.path.join(d, 'DONE'), 'w').write(lock['hash'])


def fetch_character(char):
    dst = os.path.join(manifest.ROOT, char['source']['file'])
    if not os.path.exists(dst) and char['source'].get('url'):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        print('fetching', char['source']['url'])
        urllib.request.urlretrieve(char['source']['url'], dst)
    return dst


def build(take, quality=None, to='render', force=()):
    fetch_character(manifest.resolve(take, quality)['character'])
    lock = manifest.resolve(take, quality)
    dirs = {s: manifest.stage_dir(lock, s) for s in STAGES}
    for s in STAGES:
        d = dirs[s]
        if done(d) and s not in force and 'all' not in force:
            print(f'[{s}] cached {lock["keys"][s]}')
        else:
            os.makedirs(d, exist_ok=True)
            t0 = time.time()
            if s == 'character':
                from .character import import_rig
                argv = [os.path.join(manifest.ROOT, lock['character']['source']['file']),
                        '--out', d, '--name', lock['character']['name']]
                if lock['character'].get('bone_map'):
                    mp = os.path.join(d, 'map.json')
                    json.dump(lock['character']['bone_map'], open(mp, 'w'))
                    argv += ['--map', mp]
                if lock['character'].get('outfit'):
                    oc = dict(lock['character']['outfit'])
                    oc['file'] = os.path.join(manifest.ROOT, oc['file'])
                    op = os.path.join(d, 'outfit.json')
                    json.dump(oc, open(op, 'w'))
                    argv += ['--outfit', op]
                import_rig.main(argv)
            elif s == 'body':
                from .body import gen_body
                import shutil
                for f in ('skeleton.json', 'skin.npz'):
                    shutil.copy(os.path.join(dirs['character'], f), d)
                spec = gen_body.build(d, lock['character']['mass'])
                json.dump(spec, open(os.path.join(d, 'body.json'), 'w'))
            elif s == 'sim':
                from .sim import run
                out = run.run(lock, dirs['body'], d)
                if not bool(out['ok']):
                    print('[sim] UNSTABLE: solver warning or non-finite state')
            elif s == 'qa':
                from .qa import gates
                rep = gates.check(os.path.join(dirs['sim'], 'sim.npz'), lock)
                json.dump(rep, open(os.path.join(d, 'qa.json'), 'w'), indent=1)
                gates.show(rep)
                if not rep['pass'] and 'noqa' not in force:
                    mark(d, lock)
                    print('[qa] FAILED - chain stopped before bake/render')
                    return lock, dirs, False
            elif s == 'bake':
                from .bake import bake
                bake.run(lock, dirs['character'], dirs['sim'], d)
            elif s == 'render':
                from .render import render
                render.run(lock, dirs['bake'], dirs['sim'], d)
            mark(d, lock)
            print(f'[{s}] built {lock["keys"][s]} in {time.time() - t0:.1f}s -> {d}')
        if s == 'qa' and done(d):
            rep = json.load(open(os.path.join(d, 'qa.json')))
            if not rep['pass'] and 'noqa' not in force:
                print('[qa] FAILED (cached) - chain stopped')
                return lock, dirs, False
        if s == to:
            break
    return lock, dirs, True


def main(argv=None):
    ap = argparse.ArgumentParser(prog='ko')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('take')
    b.add_argument('--quality', choices=['draft', 'full'])
    b.add_argument('--to', default='render', choices=STAGES)
    b.add_argument('--force', action='append', default=[],
                   help='stage to rebuild, "all", or "noqa" to continue past a failed QA gate')
    st = sub.add_parser('stills', help='cheap look check: key-moment stills per shot + face check')
    st.add_argument('take')
    i = sub.add_parser('import', help='lock any rig file as a character and report the bone map')
    i.add_argument('src')
    i.add_argument('--name', required=True)
    i.add_argument('--map')
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        _, _, ok = build(a.take, a.quality, a.to, a.force)
        sys.exit(0 if ok else 2)
    if a.cmd == 'stills':
        lock, dirs, ok = build(a.take, None, 'bake', ['noqa'])
        from .render import render
        out = os.path.join(manifest.ROOT, 'build', 'stills', lock['keys']['render'])
        os.makedirs(out, exist_ok=True)
        render.run(lock, dirs['bake'], dirs['sim'], out, stills=True)
        print('[stills]', out)
    if a.cmd == 'import':
        from .character import import_rig
        out = os.path.join(manifest.ROOT, 'build', 'import_preview', a.name)
        argv2 = [a.src, '--out', out, '--name', a.name] + (['--map', a.map] if a.map else [])
        import_rig.main(argv2)
        print(f'\nIf the map above is right, add presets/characters/{a.name}.yaml pointing at '
              f'the file; fix wrong entries under bone_map.')


if __name__ == '__main__':
    main()
