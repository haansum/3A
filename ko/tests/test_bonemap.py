from ko.character.bonemap import auto_map, CANON


def chain(*names, parent=None):
    out = {}
    for n in names:
        out[n] = parent
        parent = n
    return out


def rig(fmt_center, fmt_side, spine):
    b = chain(*[fmt_center(s) for s in spine])
    hips, top = fmt_center(spine[0]), None
    names = list(b)
    head = names[-1]
    fork = names[-3]
    for S in ('Left', 'Right'):
        b.update(chain(*[fmt_side(S, x) for x in ('Shoulder', 'Arm', 'ForeArm', 'Hand')], parent=fork))
        b.update(chain(*[fmt_side(S, x) for x in ('UpLeg', 'Leg', 'Foot', 'ToeBase')], parent=hips))
    return b


def test_mixamo():
    b = rig(lambda s: f'mixamorig:{s}', lambda S, x: f'mixamorig:{S}{x}',
            ['Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head'])
    m, rep = auto_map(b)
    assert m['pelvis'] == 'mixamorig:Hips' and m['head'] == 'mixamorig:Head'
    assert m['upper_arm_L'] == 'mixamorig:LeftArm' and m['forearm_R'] == 'mixamorig:RightForeArm'
    assert m['thigh_L'] == 'mixamorig:LeftUpLeg' and m['shin_R'] == 'mixamorig:RightLeg'
    assert m['spine'] == 'mixamorig:Spine' and m['neck'] == 'mixamorig:Neck'
    assert m['chest'] in ('mixamorig:Spine1', 'mixamorig:Spine2')
    assert all(m[k] for k in CANON)


def test_vroid():
    b = chain('Root', 'J_Bip_C_Hips', 'J_Bip_C_Spine', 'J_Bip_C_Chest', 'J_Bip_C_UpperChest',
              'J_Bip_C_Neck', 'J_Bip_C_Head')
    for s in 'LR':
        b.update(chain(f'J_Bip_{s}_Shoulder', f'J_Bip_{s}_UpperArm', f'J_Bip_{s}_LowerArm',
                       f'J_Bip_{s}_Hand', parent='J_Bip_C_UpperChest'))
        b.update(chain(f'J_Bip_{s}_UpperLeg', f'J_Bip_{s}_LowerLeg', f'J_Bip_{s}_Foot',
                       f'J_Bip_{s}_ToeBase', parent='J_Bip_C_Hips'))
        b[f'J_Sec_{s}_Bust1'] = 'J_Bip_C_UpperChest'
    b['J_Sec_Hair1_01'] = 'J_Bip_C_Head'
    m, rep = auto_map(b)
    assert m['pelvis'] == 'J_Bip_C_Hips' and m['thigh_R'] == 'J_Bip_R_UpperLeg'
    assert m['forearm_L'] == 'J_Bip_L_LowerArm' and m['shin_L'] == 'J_Bip_L_LowerLeg'
    assert m['spine'] == 'J_Bip_C_Spine' and m['chest'] == 'J_Bip_C_Chest'
    assert m['neck'] == 'J_Bip_C_Neck'


def test_rigify():
    b = chain('root', 'DEF-spine', 'DEF-spine.001', 'DEF-spine.002', 'DEF-spine.003',
              'DEF-spine.004', 'DEF-spine.005', 'DEF-spine.006')
    for s in 'LR':
        b.update(chain(f'DEF-shoulder.{s}', f'DEF-upper_arm.{s}', f'DEF-upper_arm.{s}.001',
                       f'DEF-forearm.{s}', f'DEF-forearm.{s}.001', f'DEF-hand.{s}',
                       parent='DEF-spine.003'))
        b.update(chain(f'DEF-thigh.{s}', f'DEF-thigh.{s}.001', f'DEF-shin.{s}',
                       f'DEF-shin.{s}.001', f'DEF-foot.{s}', f'DEF-toe.{s}', parent='DEF-spine'))
    m, rep = auto_map(b, override={'head': 'DEF-spine.006'})
    assert m['pelvis'] == 'DEF-spine' and m['upper_arm_L'] == 'DEF-upper_arm.L'
    assert m['shin_R'] == 'DEF-shin.R' and m['foot_L'] == 'DEF-foot.L'
    assert m['neck'] == 'DEF-spine.004'
