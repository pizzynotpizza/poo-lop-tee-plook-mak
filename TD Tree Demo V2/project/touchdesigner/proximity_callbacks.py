# proximity_callbacks.py
# Script CHOP "proximity" in /project1.
# Decides whether a person stands close enough to the camera.
#
# Source = Orbbec : uses real depth. Person = pixels between Mindistance and
#                   Triggerdistance (meters). Near when their area >= Minarea.
# Source = Webcam : simulation without depth. Person = pixels that differ from a
#                   captured empty background. Closer person covers more of the
#                   frame, so near when covered area >= Webcamarea.
#
# Output channels: present (0/1), area (0..1), x (0..1 body centre), nearest (m, Orbbec only)

import numpy as np

_bg = {'img': None, 'want': True}


def onSetupParameters(scriptOp):
	page = scriptOp.appendCustomPage('Proximity')
	p = page.appendMenu('Source', label='Input Source')[0]
	p.menuNames = ['webcam', 'orbbec']
	p.menuLabels = ['Webcam (simulate)', 'Orbbec Depth']
	p.default = 'webcam'

	def f(name, label, val, hi):
		q = page.appendFloat(name, label=label)[0]
		q.default = val
		q.normMax = hi

	f('Triggerdistance', 'Trigger Distance (m)', 1.2, 5)
	f('Mindistance', 'Min Distance (m)', 0.25, 2)
	f('Minarea', 'Orbbec Min Area', 0.04, 0.5)
	f('Depthscale', 'Depth Unit -> Meter (0=auto)', 0.0, 1)
	f('Webcamthreshold', 'Webcam Diff Threshold', 0.12, 0.5)
	f('Webcamarea', 'Webcam Near Area', 0.30, 1)
	page.appendToggle('Mirrorx', label='Mirror X')[0].default = True
	page.appendPulse('Capturebackground', label='Capture Empty Background')
	return


def onPulse(par):
	if par.name == 'Capturebackground':
		_bg['want'] = True
	return


def _webcam(P):
	img = op('webcam_small').numpyArray()[:, :, 0].astype('float32')
	if _bg['want'] or _bg['img'] is None or _bg['img'].shape != img.shape:
		_bg['img'] = img.copy()
		_bg['want'] = False
	mask = np.abs(img - _bg['img']) > float(P.Webcamthreshold)
	return mask, float(mask.mean()) >= float(P.Webcamarea), 0.0


def _orbbec(P):
	dep = op('depth_small').numpyArray()[:, :, 0].astype('float32')
	valid = dep > 0.0
	if not valid.any():
		return valid, False, 0.0
	unit = float(P.Depthscale)
	if unit <= 0.0:
		mx = float(dep[valid].max())
		unit = 0.001 if mx > 20.0 else (65.535 if mx <= 1.0 else 1.0)
	m = dep * unit
	mask = valid & (m >= float(P.Mindistance)) & (m <= float(P.Triggerdistance))
	return mask, float(mask.mean()) >= float(P.Minarea), float(m[valid].min())


def onCook(scriptOp):
	P = scriptOp.par
	try:
		mask, near, nearest = _webcam(P) if P.Source == 'webcam' else _orbbec(P)
	except Exception as e:
		scriptOp.addError('proximity: %s' % e)
		mask, near, nearest = None, False, 0.0
	area = float(mask.mean()) if mask is not None else 0.0
	x = 0.5
	cols = np.nonzero(mask)[1] if near else []
	if len(cols):
		x = float(cols.mean()) / max(1, mask.shape[1] - 1)
		if P.Mirrorx:
			x = 1.0 - x
	scriptOp.clear()
	scriptOp.numSamples = 1
	for name, v in (('present', 1.0 if near else 0.0), ('area', area), ('x', x), ('nearest', nearest)):
		scriptOp.appendChan(name)[0] = v
	return
