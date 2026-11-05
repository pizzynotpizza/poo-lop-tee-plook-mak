# build_network.py
# Run INSIDE TouchDesigner (Textport):
#     exec(open(project.folder + '/project/touchdesigner/build_network.py', encoding='utf-8').read())
#
# Creates /project1/tree_interaction (or tree_interaction1, 2 ... if the name is taken),
# with custom parameters, all sub networks, expressions, callbacks and in-network
# annotations. It never deletes or edits anything else in /project1.
# To rebuild over an existing component on purpose:  build(overwrite=True)

import os

PARENT_PATH = '/project1'
TARGET_NAME = 'tree_interaction'
REL_TD_DIR = 'project/touchdesigner'          # relative to the .toe folder
CANVAS = 1024                                 # square stage canvas (pixels)

COLORS = {
	'controls': (0.55, 0.50, 0.20), 'tracking_input': (0.20, 0.35, 0.60),
	'tracking_process': (0.15, 0.48, 0.48), 'growth_controller': (0.62, 0.38, 0.12),
	'tree_assets': (0.22, 0.48, 0.22), 'tree_animation': (0.42, 0.26, 0.58),
	'output': (0.60, 0.20, 0.22), 'debug': (0.35, 0.35, 0.35), 'root': (0.25, 0.25, 0.25),
}

# ------------------------------------------------------------------ section texts (Thai)

SECTION_DOCS = {
	'controls': ('CONTROLS — ค่าควบคุม',
		'หน้าที่: รับการกดปุ่ม/เปลี่ยนค่าใน Custom Parameters ของ tree_interaction\n'
		'ข้อมูลเข้า: Custom Parameters (Reset, Reanalyze, Stage1-4path)\n'
		'ข้อมูลออก: สั่ง reset state machine และวิเคราะห์ภาพใหม่\n'
		'ค่าที่ควรปรับ: ทุกค่าอยู่ที่ tree_interaction > หน้า Tracking/Animation/Assets/Output/Testing\n'
		'ข้อควรระวัง: Testmode=On จะไม่ใช้ข้อมูลจากกล้องเลย'),
	'tracking_input': ('WEBCAM + MEDIAPIPE INPUT',
		'หน้าที่: รับตำแหน่งฝ่ามือจาก Python (hand_tracker.py) ที่ประมวลผล Webcam ด้วย MediaPipe\n'
		'ข้อมูลเข้า: JSON ผ่าน UDP พอร์ต Udport (ค่าเริ่มต้น 5005)\n'
		'ข้อมูลออก: packet ล่าสุด + เวลารับ (storage: last_packet, udp_stats)\n'
		'ค่าที่ควรปรับ: Udport, Trackingtimeout\n'
		'ข้อควรระวัง: ถ้าไม่มี packet เกิน Trackingtimeout ระบบถือว่าการติดตามขาด\n'
		'ไม่ค้าง hand_present=true ตลอดไป'),
	'tracking_process': ('TRACKING PROCESS — แปลงพิกัด + smoothing',
		'หน้าที่: เปลี่ยน packet เป็น CHOP, mirror แกน X (จุดเดียวของระบบ), กลับแกน Y, smoothing\n'
		'ข้อมูลเข้า: last_packet (frame_tick เขียนลง hand_coords ทุกเฟรม)\n'
		'ข้อมูลออก: hand_raw_out (ดิบ), hand_smooth_out (hand_x, hand_y, hand_scale หลัง Lag)\n'
		'ค่าที่ควรปรับ: Mirrorx, Positionsmooth\n'
		'ข้อควรระวัง: ไม่ smooth hand_present (ใช้ hold/grace/timeout แทน)\n'
		'การเลือกมือหลักทำใน Python ด้วยความต่อเนื่องของตำแหน่ง'),
	'growth_controller': ('GROWTH CONTROLLER — state machine',
		'หน้าที่: IDLE -> GROWING -> MATURE -> DISAPPEARING, growth/opacity/anchor\n'
		'ข้อมูลเข้า: hand_coords, hand_smooth_out, Custom Parameters\n'
		'ข้อมูลออก: growth_out (state, growth, opacity, anchor_x/y, tree_scale, seg, blend_w ...)\n'
		'ค่าที่ควรปรับ: Growduration, Disappearduration, Detectionhold, Lostgrace, Returnfadetime\n'
		'ข้อควรระวัง: เวลาใช้ time.monotonic() ไม่ผูกกับ FPS\n'
		'ต้นไม้หายสนิทภายใน Disappearduration นับจากข้อมูลมือครั้งล่าสุด (รวม Lostgrace)'),
	'tree_assets': ('TREE ASSETS — ภาพ 4 ระยะ',
		'หน้าที่: โหลด PNG 4 ระยะ ตรวจ alpha จริง และจัดลง canvas สี่เหลี่ยม %dx%d\n'
		'โคนต้นตรงกันที่กึ่งกลางล่าง ความสูงต้นเท่ากัน ไม่ยืดภาพ\n'
		'ข้อมูลเข้า: Stage1path..Stage4path\n'
		'ข้อมูลออก: stage_01_out .. stage_04_out (RGBA premultiplied)\n'
		'ค่าที่ควรปรับ: path ของภาพ แล้วกด Reanalyze\n'
		'ข้อควรระวัง: ภาพที่ไม่มี alpha จะถูกรายงานใน asset_info / debug' % (CANVAS, CANVAS)),
	'tree_animation': ('TREE ANIMATION — crossfade + reveal + sway',
		'หน้าที่: blend ภาพ 2 ระยะที่ติดกัน (น้ำหนักรวม = 1), reveal จากล่างขึ้นบน,\n'
		'โยกเบา ๆ รอบโคนต้น, ขยายจากโคนต้น, วางต้นไม้ตาม anchor\n'
		'ข้อมูลเข้า: stage_0N_out, growth_out\n'
		'ข้อมูลออก: tree_rgba_out (ต้นไม้พื้นโปร่งใส ขนาด Outputwidth x Outputheight)\n'
		'ค่าที่ควรปรับ: Treesize, Treeoffsety, Swayamount, Swayspeed, Stagescales\n'
		'ข้อควรระวัง: เป็นภาพลวงตาของการเติบโตจากภาพ 2D ไม่ใช่การ morph กิ่ง/สร้าง geometry'),
	'output': ('OUTPUT',
		'หน้าที่: วางต้นไม้บนพื้นหลัง และเลือกแสดง debug overlay\n'
		'ข้อมูลเข้า: tree_rgba_out, Backgroundpath, debug_out\n'
		'ข้อมูลออก: OUT_TREE_RGBA (โปร่งใส), OUT_FINAL (ภาพแสดงจริง), output_window\n'
		'ค่าที่ควรปรับ: Outputwidth, Outputheight, Showdebug\n'
		'ข้อควรระวัง: output_window ยังไม่เปิดเอง กด Open ที่ output_window เมื่อพร้อม'),
	'debug': ('DEBUG',
		'หน้าที่: แสดงสถานะ UDP/กล้อง, ตำแหน่งมือ, state, growth, opacity,\n'
		'เวลาคงเหลือก่อนหาย, FPS, error ล่าสุด\n'
		'ข้อมูลเข้า: storage ของ tracking_input, growth_state, perform\n'
		'ข้อมูลออก: debug_out (text overlay)\n'
		'ค่าที่ควรปรับ: Showdebug\n'
		'ข้อควรระวัง: ปิด Showdebug ตอนแสดงงานจริงเพื่อลดภาระ'),
}

# per-node docs: name -> (thai description, input, output, key parameters)
NODE_DOCS = {}


def doc(name, desc, src, dst, params):
	NODE_DOCS[name] = (desc, src, dst, params)


# ------------------------------------------------------------------ small helpers

def _unique_name(parent, base):
	if parent.op(base) is None:
		return base
	i = 1
	while parent.op('%s%d' % (base, i)) is not None:
		i += 1
	return '%s%d' % (base, i)


def _mk(comp, optype, name, x, y, comment=''):
	o = comp.create(optype, name)
	o.nodeX, o.nodeY = x, y
	if comment:
		o.comment = comment
	return o


def _const_chop(chop, names, values=None):
	chop.seq.const.numBlocks = len(names)
	for i, n in enumerate(names):
		chop.par['const%dname' % i] = n
		chop.par['const%dvalue' % i] = values[i] if values else 0.0


def _expr(par, text):
	par.expr = text
	par.mode = ParMode.EXPRESSION


def _synced_text(comp, name, filename, x, y):
	d = _mk(comp, textDAT, name, x, y)
	d.par.file = REL_TD_DIR + '/' + filename
	d.par.syncfile = True
	d.par.loadonstartpulse.pulse()
	return d


def _annotate(comp, name, mode, title, body, x, y, w, h, color):
	a = comp.create(annotateCOMP, name)
	try:
		a.name = name          # this build ignores the name argument for annotations
	except Exception:
		pass
	a.par.Mode = mode
	a.par.Titletext = title
	a.par.Bodytext = body
	a.nodeX, a.nodeY, a.nodeWidth, a.nodeHeight = x, y, w, h
	try:
		a.par.Backcolorr, a.par.Backcolorg, a.par.Backcolorb = color
		a.par.Backcoloralpha = 0.55 if mode == 'networkbox' else 0.9
	except Exception:
		pass
	return a


def _annotate_section(comp, key, nodes):
	"""Network box around the nodes + a comment box listing every node."""
	title, body = SECTION_DOCS[key]
	color = COLORS[key]
	xs = [n.nodeX for n in nodes]
	ys = [n.nodeY for n in nodes]
	x0, x1 = min(xs) - 60, max(xs) + 220
	y0, y1 = min(ys) - 60, max(ys) + 200
	_annotate(comp, 'box_' + key, 'networkbox', title, '', x0, y0, x1 - x0, y1 - y0, color)
	# section summary comment, left of the box
	lines = body.count('\n') + 1
	_annotate(comp, 'note_section', 'comment', title, body,
	          x0, y0 - 80 - lines * 22, max(760, x1 - x0), 60 + lines * 22, color)
	# node guide comment below the summary
	parts = []
	for n in nodes:
		d = NODE_DOCS.get(n.name)
		if not d:
			continue
		parts.append('%s  [%s]\n  ทำหน้าที่: %s\n  รับจาก: %s\n  ส่งไปที่: %s\n  ค่าสำคัญ: %s'
		             % (n.name, n.OPType, d[0], d[1], d[2], d[3]))
	text = '\n\n'.join(parts)
	nlines = text.count('\n') + 1
	top = y0 - 120 - lines * 22
	_annotate(comp, 'note_nodes', 'comment', 'NODE GUIDE — ' + key, text,
	          x0, top - 60 - nlines * 21, max(760, x1 - x0), 60 + nlines * 21, color)


# ------------------------------------------------------------------ custom parameters

def _add_pars(ti):
	def page(name):
		for p in ti.customPages:
			if p.name == name:
				return p
		return ti.appendCustomPage(name)

	def f(pg, name, label, default, lo, hi, clamp_lo=True):
		p = pg.appendFloat(name, label=label)[0]
		p.default = p.val = default
		p.normMin, p.normMax = lo, hi
		p.min, p.clampMin = lo, clamp_lo
		return p

	pg = page('Tracking')
	# empty = receive UDP here (tracking_input/udp_hand_in); set to /project1/MediaPipe_Python
	# to read the packets that component receives (then udp_hand_in switches itself off)
	pg.appendCOMP('Trackingsource', label='Tracking Source COMP')
	p = pg.appendInt('Udport', label='UDP Port')[0]; p.default = p.val = 5005; p.normMin, p.normMax = 1024, 65535
	f(pg, 'Trackingtimeout', 'Tracking Timeout (s)', 1.0, 0.05, 5)
	f(pg, 'Detectionhold', 'Detection Hold (s)', 0.2, 0.0, 2)
	f(pg, 'Lostgrace', 'Lost Grace (s)', 0.5, 0.0, 5)
	p = pg.appendToggle('Mirrorx', label='Mirror X')[0]; p.default = p.val = True
	f(pg, 'Positionsmooth', 'Position Smooth (s)', 0.15, 0.0, 1)

	pg = page('Animation')
	f(pg, 'Growduration', 'Grow Duration (s)', 12.0, 0.01, 60)
	f(pg, 'Disappearduration', 'Disappear Duration (s)', 40.0, 0.1, 120)
	f(pg, 'Returnfadetime', 'Return Fade Time (s)', 0.8, 0.01, 5)
	f(pg, 'Treesize', 'Tree Size (x output height)', 0.75, 0.05, 2)
	f(pg, 'Treeoffsety', 'Tree Offset Y', 0.02, -0.5, 0.5, clamp_lo=False)
	f(pg, 'Swayamount', 'Sway Amount (deg)', 1.5, 0.0, 10)
	f(pg, 'Swayspeed', 'Sway Speed', 0.25, 0.01, 3)
	p = pg.appendStr('Stagescales', label='Stage Scales (1-4)')[0]; p.default = p.val = '0.5 0.68 0.85 1.0'

	pg = page('Assets')
	for i in range(1, 5):
		p = pg.appendFile('Stage%dpath' % i, label='Stage %d Path' % i)[0]
		p.default = p.val = 'project/assets/tree_stage_%02d.png' % i
	p = pg.appendFile('Backgroundpath', label='Background Path')[0]
	p.default = p.val = 'project/assets/background.jpg'
	pg.appendPulse('Reanalyze', label='Reanalyze Assets')

	pg = page('Output')
	p = pg.appendInt('Outputwidth', label='Output Width')[0]; p.default = p.val = 1280; p.min = 16; p.clampMin = True
	p = pg.appendInt('Outputheight', label='Output Height')[0]; p.default = p.val = 720; p.min = 16; p.clampMin = True
	p = pg.appendToggle('Showdebug', label='Show Debug')[0]; p.default = p.val = True

	pg = page('Testing')
	p = pg.appendToggle('Testmode', label='Test Mode (no camera)')[0]; p.default = p.val = False
	p = pg.appendToggle('Testhandpresent', label='Test Hand Present')[0]; p.default = p.val = False
	f(pg, 'Testhandx', 'Test Hand X (0-1)', 0.5, 0.0, 1)
	f(pg, 'Testhandy', 'Test Hand Y (0-1, up)', 0.25, 0.0, 1)
	pg.appendPulse('Reset', label='Reset')


# ------------------------------------------------------------------ sections

def _build_controls(c):
	h = _mk(c, parameterexecuteDAT, 'param_handler', 0, 0, 'Reset / Reanalyze / path changes')
	h.par.op = '..'
	h.par.pars = 'Reset Reanalyze Stage1path Stage2path Stage3path Stage4path'
	h.par.valuechange = True
	h.par.onpulse = True
	h.par.custom = True
	h.par.builtin = False
	h.text = (
		"# param_handler: reacts to custom parameters of tree_interaction\n"
		"def _ctrl():\n"
		"\treturn op('../growth_controller/animation_controller').module\n\n"
		"def onPulse(par):\n"
		"\tif par.name == 'Reset':\n"
		"\t\t_ctrl().reset()\n"
		"\telif par.name == 'Reanalyze':\n"
		"\t\trun(\"op('%s').module.analyze_assets()\", delayFrames=2)\n"
		"\treturn\n\n"
		"def onValueChange(par, prev):\n"
		"\tif par.name.startswith('Stage'):\n"
		"\t\trun(\"op('%s').module.analyze_assets()\", delayFrames=5)\n"
		"\treturn\n" % ((c.parent().path + '/growth_controller/animation_controller',) * 2))
	doc('param_handler', 'เรียก reset() เมื่อกด Reset และ analyze_assets() เมื่อกด Reanalyze หรือเปลี่ยน Stage path',
	    'Custom Parameters ของ tree_interaction', 'growth_controller/animation_controller', 'Pars = Reset Reanalyze Stage1-4path')
	_annotate_section(c, 'controls', [h])


def _build_tracking_input(c):
	cb = _synced_text(c, 'hand_json_callbacks', 'tracking_callbacks.py', 0, -160)
	cb.comment = 'onReceive: validate JSON, store last_packet'
	u = _mk(c, udpinDAT, 'udp_hand_in', 0, 0, 'UDP JSON from hand_tracker.py')
	_expr(u.par.port, 'parent.TI.par.Udport')
	u.par.format = 'permessage'
	u.par.maxlines = 20
	u.par.clamp = True
	u.par.callbacks = 'hand_json_callbacks'
	_expr(u.par.active, 'parent.TI.par.Trackingsource.eval() is None')
	auto = c.op('udp_hand_in_callbacks')     # default DAT created with the UDP In DAT, unused
	if auto is not None:
		auto.destroy()
	doc('udp_hand_in', 'รับ packet JSON จาก Python ทีละ message (ปิดตัวเองเมื่อตั้ง Trackingsource แล้ว)', 'hand_tracker.py (127.0.0.1:Udport)',
	    'hand_json_callbacks', 'Port = parent.TI.par.Udport, Active = Trackingsource ว่าง, Format = One Per Message')
	doc('hand_json_callbacks', 'ตรวจ JSON, ตรวจลำดับ seq, บันทึก packet ล่าสุด + เวลารับ (monotonic) ลง storage',
	    'udp_hand_in', 'storage ของ tracking_input -> animation_controller', 'ไฟล์ project/touchdesigner/tracking_callbacks.py (sync)')
	_annotate_section(c, 'tracking_input', [u, cb])


def _build_tracking_process(c):
	raw = _mk(c, constantCHOP, 'hand_coords', 0, 0, 'written every frame by frame_tick')
	_const_chop(raw, ['hand_present', 'hand_x', 'hand_y', 'hand_scale', 'tracking_alive', 'packet_age'])
	rawout = _mk(c, nullCHOP, 'hand_raw_out', 200, 140)
	rawout.inputConnectors[0].connect(raw)
	sel = _mk(c, selectCHOP, 'select_position', 200, 0)
	sel.inputConnectors[0].connect(raw)
	sel.par.channames = 'hand_x hand_y hand_scale'
	lag = _mk(c, lagCHOP, 'hand_smooth', 400, 0, 'smooth position only')
	lag.inputConnectors[0].connect(sel)
	lag.par.lagunit = 'seconds'
	_expr(lag.par.lag1, 'parent.TI.par.Positionsmooth')
	_expr(lag.par.lag2, 'parent.TI.par.Positionsmooth')
	out = _mk(c, nullCHOP, 'hand_smooth_out', 600, 0)
	out.inputConnectors[0].connect(lag)
	doc('hand_coords', 'ค่ามือดิบหลัง mirror/กลับแกน Y (ค้างค่าล่าสุดเมื่อไม่มีมือ)', 'animation_controller (tracking step)',
	    'hand_raw_out, select_position', 'channels: hand_present hand_x hand_y hand_scale tracking_alive packet_age')
	doc('hand_raw_out', 'จุดเชื่อมต่อค่ามือดิบ', 'hand_coords', 'debug / ผู้ใช้', '-')
	doc('select_position', 'เลือกเฉพาะตำแหน่งและขนาดมือไป smooth (ไม่ smooth hand_present)', 'hand_coords', 'hand_smooth', 'channames = hand_x hand_y hand_scale')
	doc('hand_smooth', 'Lag CHOP ทำให้ตำแหน่งลื่น', 'select_position', 'hand_smooth_out', 'Lag 1/2 = parent.TI.par.Positionsmooth (seconds)')
	doc('hand_smooth_out', 'ตำแหน่งมือที่ smooth แล้ว', 'hand_smooth', 'animation_controller (anchor)', '-')
	_annotate_section(c, 'tracking_process', [raw, rawout, sel, lag, out])


def _build_growth_controller(c):
	mod = _synced_text(c, 'animation_controller', 'animation_controller.py', 0, 0)
	mod.comment = 'state machine module, tick() each frame'
	st = _mk(c, constantCHOP, 'growth_state', 200, 0, 'written every frame')
	_const_chop(st, ['state', 'growth', 'opacity', 'anchor_x', 'anchor_y', 'tree_scale',
	                 'seg', 'blend_w', 'reveal', 'hand_confirmed', 'time_left', 'tracking_alive'])
	out = _mk(c, nullCHOP, 'growth_out', 400, 0)
	out.inputConnectors[0].connect(st)
	doc('animation_controller', 'state machine IDLE/GROWING/MATURE/DISAPPEARING, timer, opacity, anchor, reset, วิเคราะห์ภาพ',
	    'storage tracking_input, hand_smooth_out, Custom Parameters', 'hand_coords, growth_state, blend_keys, appear_keys, debug_info',
	    'ไฟล์ project/touchdesigner/animation_controller.py (sync) | tick(), reset(), analyze_assets()')
	doc('growth_state', 'เก็บผลของ state machine เป็น CHOP', 'animation_controller', 'growth_out',
	    'state 0=IDLE 1=GROWING 2=MATURE 3=DISAPPEARING, growth 0-1, opacity, anchor_x/y, tree_scale, seg, blend_w, reveal, time_left')
	doc('growth_out', 'จุดเชื่อมต่อหลักของค่าแอนิเมชัน', 'growth_state', 'tree_animation/growth_in, debug', '-')
	_annotate_section(c, 'growth_controller', [mod, st, out])


def _build_tree_assets(c):
	nodes = []
	for i in range(1, 5):
		y = -(i - 1) * 160
		m = _mk(c, moviefileinTOP, 'stage_%02d_in' % i, 0, y)
		_expr(m.par.file, 'parent.TI.par.Stage%dpath' % i)
		m.par.premultrgbbyalpha = 'on'       # PNG straight alpha -> premultiplied inside TD
		cv = _mk(c, transformTOP, 'stage_%02d_canvas' % i, 200, y, 'base -> bottom centre')
		cv.inputConnectors[0].connect(m)
		cv.par.outputresolution = 'custom'
		cv.par.resolutionw = cv.par.resolutionh = CANVAS
		cv.par.extend = 'zero'
		cv.par.xord = 'srt'
		o = _mk(c, nullTOP, 'stage_%02d_out' % i, 400, y)
		o.inputConnectors[0].connect(cv)
		nodes += [m, cv, o]
		doc(m.name, 'โหลดภาพต้นไม้ระยะ %d (RGBA)' % i, 'Stage%dpath' % i, cv.name,
		    'File = parent.TI.par.Stage%dpath, Pre-Multiply = On' % i)
		doc(cv.name, 'จัดภาพลง canvas %dx%d: โคนต้นกึ่งกลางล่าง, ความสูงต้น %.0f%% ของ canvas' % (CANVAS, CANVAS, 95),
		    m.name, o.name, 'sx/sy/px/py/tx/ty คำนวณโดย analyze_assets() จาก alpha จริง')
		doc(o.name, 'จุดเชื่อมต่อภาพระยะ %d' % i, cv.name, 'tree_animation/select_stage_%02d' % i, '-')
	info = _mk(c, tableDAT, 'asset_info', 600, 0, 'alpha / bbox report')
	nodes.append(info)
	doc('asset_info', 'รายงานผลตรวจไฟล์: มีไฟล์ไหม, PNG type (6=RGBA), สัดส่วนพื้นที่โปร่งใส, ตำแหน่งโคน, ขนาด',
	    'analyze_assets()', 'ผู้ใช้ / debug', 'status OK / MISSING FILE / NO ALPHA')
	_annotate_section(c, 'tree_assets', nodes)


def _build_tree_animation(c):
	gi = _mk(c, selectCHOP, 'growth_in', 0, 260)
	gi.par.chops = '../growth_controller/growth_out'
	sels = []
	for i in range(1, 5):
		s = _mk(c, selectTOP, 'select_stage_%02d' % i, 0, -(i - 1) * 140)
		s.par.top = '../tree_assets/stage_%02d_out' % i
		sels.append(s)
		doc(s.name, 'ดึงภาพระยะ %d จาก tree_assets' % i, 'tree_assets/stage_%02d_out' % i, 'stage_switch_a / stage_switch_b', '-')
	sa = _mk(c, switchTOP, 'stage_switch_a', 220, -60, 'current stage')
	sb = _mk(c, switchTOP, 'stage_switch_b', 220, -260, 'next stage')
	for idx, s in enumerate(sels):
		s.outputConnectors[0].connect(sa.inputConnectors[idx])
		s.outputConnectors[0].connect(sb.inputConnectors[idx])
	_expr(sa.par.index, "int(op('growth_in')['seg'])")
	_expr(sb.par.index, "min(3, int(op('growth_in')['seg']) + 1)")

	bk = _mk(c, tableDAT, 'blend_keys', 220, -460)
	ak = _mk(c, tableDAT, 'appear_keys', 640, -460)
	for t in (bk, ak):
		t.clear()
		t.appendRows([['pos', 'r', 'g', 'b', 'a'], [0, 0, 0, 0, 0], [1, 0, 0, 0, 0]])
	bm = _mk(c, rampTOP, 'blend_mask', 420, -460, 'weight map w * reveal')
	am = _mk(c, rampTOP, 'appear_mask', 840, -460, 'opacity * reveal')
	for r, k in ((bm, bk), (am, ak)):
		r.par.type = 'vertical'
		r.par.dat = k.name
		r.par.outputresolution = 'custom'
		r.par.resolutionw = r.par.resolutionh = CANVAS
		r.par.premultrgbbyalpha = False
		auto = c.op(r.name + '_keys')        # default key table created with the ramp, unused
		if auto is not None:
			auto.destroy()

	bl = _mk(c, matteTOP, 'stage_blend', 440, -160, 'B*m + A*(1-m)')
	sb.outputConnectors[0].connect(bl.inputConnectors[0])
	sa.outputConnectors[0].connect(bl.inputConnectors[1])
	bm.outputConnectors[0].connect(bl.inputConnectors[2])
	bl.par.mattechannel = 'red'

	mk = _mk(c, multiplyTOP, 'tree_masked', 640, -160, 'appear reveal + opacity')
	bl.outputConnectors[0].connect(mk.inputConnectors[0])
	am.outputConnectors[0].connect(mk.inputConnectors[1])

	nz = _mk(c, noiseCHOP, 'sway_noise', 640, 260, 'slow wind')
	nz.par.type = 'hermite'
	nz.par.channelname = 'sway'
	nz.par.periodunit = 'seconds'
	_expr(nz.par.period, '1.0 / max(0.01, parent.TI.par.Swayspeed)')
	_expr(nz.par.amp, 'parent.TI.par.Swayamount')
	nz.par.timeslice = True

	sw = _mk(c, transformTOP, 'tree_sway', 840, -160, 'rotate around trunk base')
	mk.outputConnectors[0].connect(sw.inputConnectors[0])
	sw.par.px, sw.par.py = 0.5, 0.0      # pivot fraction from bottom-left = trunk base
	sw.par.extend = 'zero'
	_expr(sw.par.rotate, "op('sway_noise')['sway']")

	pl = _mk(c, transformTOP, 'tree_place', 1040, -160, 'scale from base + move to anchor')
	sw.outputConnectors[0].connect(pl.inputConnectors[0])
	pl.par.outputresolution = 'custom'
	_expr(pl.par.resolutionw, 'parent.TI.par.Outputwidth')
	_expr(pl.par.resolutionh, 'parent.TI.par.Outputheight')
	pl.par.extend = 'zero'
	pl.par.xord = 'srt'
	pl.par.px, pl.par.py = 0.5, 0.0
	_expr(pl.par.sy, "parent.TI.par.Treesize * op('growth_in')['tree_scale']")
	_expr(pl.par.sx, "parent.TI.par.Treesize * op('growth_in')['tree_scale'] * parent.TI.par.Outputheight / parent.TI.par.Outputwidth")
	_expr(pl.par.tx, "op('growth_in')['anchor_x'] - 0.5")
	_expr(pl.par.ty, "op('growth_in')['anchor_y'] + parent.TI.par.Treeoffsety")

	out = _mk(c, nullTOP, 'tree_rgba_out', 1240, -160)
	out.inputConnectors[0].connect(pl)

	doc('growth_in', 'รับค่าแอนิเมชันจาก growth_controller', 'growth_controller/growth_out', 'expressions ทุก TOP ในส่วนนี้', '-')
	doc('stage_switch_a', 'ภาพระยะปัจจุบัน (A)', 'select_stage_01..04', 'stage_blend input 2', "Index = int(op('growth_in')['seg'])")
	doc('stage_switch_b', 'ภาพระยะถัดไป (B)', 'select_stage_01..04', 'stage_blend input 1', "Index = min(3, seg + 1)")
	doc('blend_keys', 'คีย์ ramp ของ weight map (เขียนทุกเฟรมเมื่อค่าเปลี่ยน)', 'animation_controller', 'blend_mask', 'pos r g b a, pos 0 = ล่าง')
	doc('blend_mask', 'weight map = smoothstep(t) x reveal ล่าง->บน ขอบนุ่ม', 'blend_keys', 'stage_blend input 3', 'Type = Vertical, %dx%d' % (CANVAS, CANVAS))
	doc('stage_blend', 'Matte: B*m + A*(1-m) น้ำหนักรวม = 1 ทุกพิกเซล (premultiplied จึงไม่มีขอบดำ/ภาพมืด)',
	    'stage_switch_b, stage_switch_a, blend_mask', 'tree_masked', 'Matte Channel = Red')
	doc('appear_keys', 'คีย์ ramp ของ reveal ตอนปรากฏ x opacity', 'animation_controller', 'appear_mask', 'ค่า rgba เท่ากัน (premultiplied)')
	doc('appear_mask', 'mask reveal ตอนต้นไม้ปรากฏ + opacity รวม', 'appear_keys', 'tree_masked input 2', 'Type = Vertical')
	doc('tree_masked', 'คูณ RGBA ด้วย appear_mask (คูณ opacity ครั้งเดียว ไม่ซ้ำ)', 'stage_blend, appear_mask', 'tree_sway', '-')
	doc('sway_noise', 'Noise CHOP ช้า ๆ สำหรับโยกคล้ายลม', '-', 'tree_sway.rotate', 'Type Hermite, Period = 1/Swayspeed, Amp = Swayamount (องศา)')
	doc('tree_sway', 'หมุนเล็กน้อยรอบโคนต้น โคนต้นจึงไม่ขยับ', 'tree_masked, sway_noise', 'tree_place', "Pivot = (0.5, 0) = กึ่งกลางล่าง, Rotate = op('sway_noise')['sway']")
	doc('tree_place', 'ขยายจากโคนต้นและย้ายโคนต้นไปที่ anchor (ฝ่ามือ) บนภาพขนาด output', 'tree_sway, growth_in', 'tree_rgba_out',
	    'sy = Treesize*tree_scale, sx ชดเชย aspect, tx = anchor_x-0.5, ty = anchor_y+Treeoffsety')
	doc('tree_rgba_out', 'ต้นไม้พื้นโปร่งใส', 'tree_place', 'output/select_tree', '-')
	_annotate_section(c, 'tree_animation', [gi] + sels + [sa, sb, bk, ak, bm, am, bl, mk, nz, sw, pl, out])


def _build_output(c):
	st = _mk(c, selectTOP, 'select_tree', 0, 0)
	st.par.top = '../tree_animation/tree_rgba_out'
	rgba = _mk(c, nullTOP, 'OUT_TREE_RGBA', 220, 140)
	rgba.inputConnectors[0].connect(st)
	bg = _mk(c, moviefileinTOP, 'background_in', 0, -180)
	_expr(bg.par.file, 'parent.TI.par.Backgroundpath')
	fit = _mk(c, fitTOP, 'bg_fit', 220, -180, 'fill output, keep aspect')
	fit.inputConnectors[0].connect(bg)
	fit.par.fit = 'fitoutside'
	fit.par.outputresolution = 'custom'
	_expr(fit.par.resolutionw, 'parent.TI.par.Outputwidth')
	_expr(fit.par.resolutionh, 'parent.TI.par.Outputheight')
	ov = _mk(c, overTOP, 'final_over', 440, 0, 'tree over background')
	st.outputConnectors[0].connect(ov.inputConnectors[0])
	fit.outputConnectors[0].connect(ov.inputConnectors[1])
	ov.par.size = 'input2'
	sd = _mk(c, selectTOP, 'select_debug', 440, -180)
	sd.par.top = '../debug/debug_out'
	dov = _mk(c, overTOP, 'debug_over', 640, -180)
	sd.outputConnectors[0].connect(dov.inputConnectors[0])
	ov.outputConnectors[0].connect(dov.inputConnectors[1])
	dov.par.size = 'input2'
	tg = _mk(c, switchTOP, 'debug_toggle', 840, 0)
	ov.outputConnectors[0].connect(tg.inputConnectors[0])
	dov.outputConnectors[0].connect(tg.inputConnectors[1])
	_expr(tg.par.index, 'int(parent.TI.par.Showdebug)')
	fin = _mk(c, nullTOP, 'OUT_FINAL', 1040, 0)
	fin.inputConnectors[0].connect(tg)
	win = _mk(c, windowCOMP, 'output_window', 1040, -200, 'press Open to show')
	win.par.winop = 'OUT_FINAL'
	_expr(win.par.winw, 'parent.TI.par.Outputwidth')
	_expr(win.par.winh, 'parent.TI.par.Outputheight')
	doc('select_tree', 'ดึงต้นไม้โปร่งใส', 'tree_animation/tree_rgba_out', 'OUT_TREE_RGBA, final_over', '-')
	doc('OUT_TREE_RGBA', 'ผลลัพธ์ต้นไม้พื้นโปร่งใส (ใช้ต่อกับระบบอื่นได้)', 'select_tree', 'ภายนอก', '-')
	doc('background_in', 'โหลดภาพพื้นหลัง', 'Backgroundpath', 'bg_fit', 'File = parent.TI.par.Backgroundpath')
	doc('bg_fit', 'ปรับพื้นหลังให้เต็มจอโดยไม่ยืด', 'background_in', 'final_over input 2', 'Fit = Fit Outside, Resolution = Outputwidth x Outputheight')
	doc('final_over', 'วางต้นไม้ทับพื้นหลัง', 'select_tree, bg_fit', 'debug_toggle, debug_over', 'Size = Input 2')
	doc('select_debug', 'ดึงข้อความ debug', 'debug/debug_out', 'debug_over', '-')
	doc('debug_over', 'วางข้อความ debug ทับภาพ', 'select_debug, final_over', 'debug_toggle', '-')
	doc('debug_toggle', 'เลือกแสดง/ไม่แสดง debug', 'final_over, debug_over', 'OUT_FINAL', 'Index = int(parent.TI.par.Showdebug)')
	doc('OUT_FINAL', 'ภาพแสดงจริง', 'debug_toggle', 'output_window', '-')
	doc('output_window', 'หน้าต่างแสดงผล (ยังไม่เปิดอัตโนมัติ)', 'OUT_FINAL', 'จอแสดงผล', 'Window Operator = OUT_FINAL, ขนาด = Output')
	_annotate_section(c, 'output', [st, rgba, bg, fit, ov, sd, dov, tg, fin, win])


def _build_debug(c):
	pf = _mk(c, performCHOP, 'perform', 0, 0)
	try:
		pf.par.fps = True
	except Exception:
		pass
	info = _mk(c, tableDAT, 'debug_info', 0, -160, 'status table')
	tx = _mk(c, textTOP, 'debug_text', 220, -160)
	tx.par.outputresolution = 'custom'
	_expr(tx.par.resolutionw, 'parent.TI.par.Outputwidth')
	_expr(tx.par.resolutionh, 'parent.TI.par.Outputheight')
	tx.par.bgalpha = 0.0
	tx.par.fontsizex = 15
	for name, val in (('alignx', 'left'), ('aligny', 'top'), ('font', 'Consolas')):
		try:
			setattr(tx.par, name, val)
		except Exception:
			pass
	tx.par.positionx, tx.par.positiony = 12, -12
	out = _mk(c, nullTOP, 'debug_out', 420, -160)
	out.inputConnectors[0].connect(tx)
	doc('perform', 'วัด FPS ของ TouchDesigner', '-', 'animation_controller (debug step)', 'FPS = On')
	doc('debug_info', 'ตารางสถานะ (state, growth, opacity, UDP, มือ, เวลาคงเหลือ, FPS, error)', 'animation_controller', 'ผู้ใช้', 'อัปเดตเมื่อ Showdebug = On')
	doc('debug_text', 'ข้อความสถานะสำหรับ overlay', 'animation_controller', 'debug_out', 'พื้นโปร่งใส ขนาดเท่า output')
	doc('debug_out', 'จุดเชื่อมต่อ debug overlay', 'debug_text', 'output/select_debug', '-')
	_annotate_section(c, 'debug', [pf, info, tx, out])


# ------------------------------------------------------------------ main

SECTIONS = [
	('controls', _build_controls), ('tracking_input', _build_tracking_input),
	('tracking_process', _build_tracking_process), ('growth_controller', _build_growth_controller),
	('tree_assets', _build_tree_assets), ('tree_animation', _build_tree_animation),
	('output', _build_output), ('debug', _build_debug),
]


def build(overwrite=False, name=TARGET_NAME):
	parent_op = op(PARENT_PATH)
	missing = [f for f in ('animation_controller.py', 'tracking_callbacks.py')
	           if not os.path.isfile(os.path.join(project.folder, REL_TD_DIR, f))]
	if missing:
		raise FileNotFoundError('missing %s in %s/%s' % (missing, project.folder, REL_TD_DIR))
	existing = parent_op.op(name)
	if existing is not None:
		if overwrite:
			existing.destroy()
		else:
			name = _unique_name(parent_op, name)
			print('[build_network] %s/%s exists -> building %s instead (use build(overwrite=True) to replace)'
			      % (PARENT_PATH, TARGET_NAME, name))
	NODE_DOCS.clear()
	xs = [c.nodeX for c in parent_op.children] or [0]
	ti = parent_op.create(baseCOMP, name)
	ti.nodeX, ti.nodeY = max(xs) + 400, 0
	ti.par.parentshortcut = 'TI'
	ti.comment = 'Tree growth interaction (MediaPipe Python -> UDP)'
	ti.color = COLORS['root']
	_add_pars(ti)

	spacing = 520
	for i, (key, fn) in enumerate(SECTIONS):
		c = ti.create(baseCOMP, key)
		c.nodeX, c.nodeY = i * spacing, 0
		c.color = COLORS[key]
		c.comment = SECTION_DOCS[key][0]
		fn(c)
		title, body = SECTION_DOCS[key]
		lines = body.count('\n') + 1
		# network box = grouping only; the comment box below carries the text
		_annotate(ti, 'box_' + key, 'networkbox', '%d. %s' % (i + 1, title), '',
		          c.nodeX - 60, -60, 470, 240, COLORS[key])
		_annotate(ti, 'note_' + key, 'comment', '%d. %s' % (i + 1, title), body,
		          c.nodeX - 60, -100 - (60 + lines * 24), 470, 60 + lines * 24, COLORS[key])

	tick = ti.create(executeDAT, 'frame_tick')
	tick.nodeX, tick.nodeY = 0, 320
	tick.comment = 'calls animation_controller.tick() every frame'
	tick.text = (
		"# frame_tick: one tick per frame on the main thread\n"
		"def onFrameStart(frame):\n"
		"\ttry:\n"
		"\t\top('growth_controller/animation_controller').module.tick()\n"
		"\texcept Exception as e:\n"
		"\t\tmsg = 'tick error: %s' % e\n"
		"\t\tif parent().fetch('tick_error', '', search=False) != msg:\n"
		"\t\t\tparent().store('tick_error', msg)\n"
		"\t\t\tprint('[tree_interaction]', msg)\n"
		"\treturn\n")
	tick.par.framestart = True
	tick.par.active = True
	_annotate(ti, 'note_overview', 'comment', 'TREE HAND TRACKING — ภาพรวมเส้นทางข้อมูล (อ่านซ้ายไปขวา)',
		'hand_tracker.py (OpenCV + MediaPipe) -> UDP 5005 -> 2 tracking_input -> 3 tracking_process\n'
		'-> 4 growth_controller (state machine) -> 5 tree_assets + 6 tree_animation -> 7 output (OUT_FINAL)\n'
		'frame_tick (Execute DAT) เรียก animation_controller.tick() ทุกเฟรมบน main thread\n'
		'ค่าที่ปรับได้ทั้งหมดอยู่ที่ Custom Parameters ของ COMP นี้ (tree_interaction)\n'
		'ทดสอบโดยไม่ใช้กล้อง: Testing > Testmode = On แล้วเปิด Testhandpresent',
		220, 300, 1600, 200, COLORS['root'])

	mod = ti.op('growth_controller/animation_controller').module
	errs = mod.analyze_assets()
	mod.reset()
	print('[build_network] built %s  | asset errors: %s' % (ti.path, errs or 'none'))
	return ti


if globals().get('AUTO_BUILD', True):     # build_mediapipe_python.py sets AUTO_BUILD = False to reuse helpers
	_built = build()
