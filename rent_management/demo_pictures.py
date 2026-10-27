# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Illustrated photos for the demo data: building fronts and flat avatar portraits."""

import base64
import io

from PIL import Image, ImageDraw, ImageFilter

SCALE = 2  # drawn at twice the size and scaled down, for smooth edges

SKIN = [(241, 194, 150), (224, 172, 125), (198, 140, 96), (166, 110, 70), (130, 84, 52)]
HAIR = [(33, 26, 23), (24, 20, 20), (58, 38, 28), (78, 52, 36)]
SHIRTS = [(79, 70, 229), (14, 165, 233), (16, 185, 129), (244, 114, 82), (234, 179, 8), (100, 116, 139)]
BACKDROPS = [(224, 231, 255), (209, 250, 229), (254, 243, 199), (224, 242, 254), (255, 228, 230)]
WALLS = [(244, 226, 198), (214, 141, 108), (196, 214, 190), (230, 222, 210)]


def to_data_url(image) -> str:
	buffer = io.BytesIO()
	image.convert("RGB").save(buffer, "JPEG", quality=86)
	return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def avatar(rng, gender) -> str:
	size = 480 * SCALE
	s = size / 480
	image = Image.new("RGB", (size, size), rng.choice(BACKDROPS))
	draw = ImageDraw.Draw(image)
	skin, hair, shirt = rng.choice(SKIN), rng.choice(HAIR), rng.choice(SHIRTS)
	female = gender == "Female"

	def box(x0, y0, x1, y1):
		return [x0 * s, y0 * s, x1 * s, y1 * s]

	if female:  # long hair falls behind the shoulders
		draw.rounded_rectangle(box(130, 150, 350, 390), radius=90 * s, fill=hair)
	draw.ellipse(box(70, 330, 410, 620), fill=shirt)  # shoulders
	draw.rectangle(box(205, 270, 275, 350), fill=skin)  # neck
	draw.ellipse(box(205, 315, 275, 365), fill=skin)
	draw.ellipse(box(150, 120, 330, 320), fill=skin)  # head
	draw.ellipse(box(140, 200, 165, 250), fill=skin)  # ears
	draw.ellipse(box(315, 200, 340, 250), fill=skin)
	if female:
		draw.chord(box(140, 100, 340, 260), 180, 360, fill=hair)
		draw.pieslice(box(150, 110, 290, 250), 180, 300, fill=hair)
	else:
		draw.chord(box(145, 100, 335, 230), 180, 360, fill=hair)
		draw.rectangle(box(150, 160, 170, 205), fill=hair)
		draw.rectangle(box(310, 160, 330, 205), fill=hair)
	eye = (40, 32, 30)
	draw.ellipse(box(200, 215, 214, 229), fill=eye)
	draw.ellipse(box(266, 215, 280, 229), fill=eye)
	draw.arc(box(212, 245, 268, 285), 20, 160, fill=(150, 80, 70), width=int(5 * s))
	collar = tuple(max(c - 40, 0) for c in shirt)
	draw.polygon([(205 * s, 355 * s), (240 * s, 400 * s), (275 * s, 355 * s)], fill=collar)
	return to_data_url(image.resize((480, 480), Image.LANCZOS))


def building(rng, floors=4) -> str:
	w, h = 1280 * SCALE, 720 * SCALE
	image = Image.new("RGB", (w, h))
	draw = ImageDraw.Draw(image)
	top, bottom = (135, 190, 240), (214, 234, 248)
	for y in range(h):  # sky
		t = y / h
		draw.line(
			[(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True))
		)
	draw.ellipse([w * 0.8, h * 0.08, w * 0.88, h * 0.22], fill=(255, 236, 170))
	for _i in range(3):  # clouds
		x, y = rng.uniform(0.05, 0.7) * w, rng.uniform(0.06, 0.25) * h
		for dx, dy, r in ((0, 0, 60), (55, -20, 70), (115, 0, 55)):
			r *= SCALE
			draw.ellipse(
				[x + dx * SCALE - r, y + dy * SCALE - r, x + dx * SCALE + r, y + dy * SCALE + r], fill="white"
			)
	ground = h * 0.84

	# neighbours, faded
	for x0, x1, height in ((0.0, 0.2, 0.42), (0.8, 1.0, 0.5)):
		draw.rectangle([x0 * w, ground - height * h, x1 * w, ground], fill=(196, 206, 218))
		for fx in range(int(x0 * 20) + 1, int(x1 * 20)):
			for fy in range(3):
				y = ground - height * h + (40 + fy * 90) * SCALE
				draw.rectangle(
					[fx * w / 20, y, fx * w / 20 + 24 * SCALE, y + 40 * SCALE], fill=(176, 188, 204)
				)

	wall = rng.choice(WALLS)
	trim = tuple(max(c - 45, 0) for c in wall)
	left, right = w * 0.25, w * 0.75
	floor_h = 118 * SCALE
	roof = ground - floors * floor_h - 30 * SCALE
	draw.rectangle([left, roof, right, ground], fill=wall)
	draw.rectangle([left - 20 * SCALE, roof - 26 * SCALE, right + 20 * SCALE, roof + 4 * SCALE], fill=trim)
	columns = 6
	cell = (right - left) / columns
	for floor in range(floors):
		y = roof + 40 * SCALE + floor * floor_h
		if floor:  # balcony line
			draw.rectangle([left, y - 18 * SCALE, right, y - 10 * SCALE], fill=trim)
		for c in range(columns):
			x = left + c * cell + cell * 0.22
			if floor == floors - 1 and c in (2, 3):
				continue  # the entrance
			lit = rng.random() < 0.25
			draw.rectangle(
				[x - 6 * SCALE, y - 6 * SCALE, x + cell * 0.56 + 6 * SCALE, y + 66 * SCALE],
				fill=(250, 250, 248),
			)
			draw.rectangle(
				[x, y, x + cell * 0.56, y + 60 * SCALE], fill=(255, 226, 150) if lit else (120, 170, 210)
			)
			draw.line(
				[x + cell * 0.28, y, x + cell * 0.28, y + 60 * SCALE], fill=(250, 250, 248), width=4 * SCALE
			)
	door_l, door_r = left + cell * 2.25, left + cell * 3.75
	draw.rectangle([door_l, ground - 100 * SCALE, door_r, ground], fill=(92, 64, 51))
	draw.line(
		[(door_l + door_r) / 2, ground - 100 * SCALE, (door_l + door_r) / 2, ground],
		fill=(70, 48, 38),
		width=4 * SCALE,
	)
	draw.rounded_rectangle([door_l - 30 * SCALE, ground - 150 * SCALE, door_r + 30 * SCALE, ground - 112 * SCALE],
		radius=8 * SCALE, fill=(79, 70, 229))  # fmt: skip

	draw.rectangle([0, ground, w, h], fill=(170, 178, 168))  # pavement
	draw.rectangle([0, ground, w, ground + 14 * SCALE], fill=(150, 158, 150))
	for x in (0.13, 0.87):  # trees
		cx = x * w
		draw.rectangle([cx - 9 * SCALE, ground - 120 * SCALE, cx + 9 * SCALE, ground], fill=(110, 78, 50))
		for dx, dy, r in ((0, -170, 80), (-55, -130, 60), (55, -130, 60)):
			draw.ellipse([cx + (dx - r) * SCALE, ground + (dy - r) * SCALE, cx + (dx + r) * SCALE, ground + (dy + r) * SCALE],
				fill=(76, 150, 90))  # fmt: skip
	image = image.filter(ImageFilter.SMOOTH)
	return to_data_url(image.resize((1280, 720), Image.LANCZOS))
