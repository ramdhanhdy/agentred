from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, textwrap

OUT = Path('/opt/data/projects/agentred/docs/agentred-operational-workflow-architecture.png')
W, H = 2000, 1250
S = 2
img = Image.new('RGBA', (W*S, H*S), (2, 6, 23, 255))
draw = ImageDraw.Draw(img, 'RGBA')

def C(hexv, a=255):
    hexv = hexv.lstrip('#')
    return tuple(int(hexv[i:i+2], 16) for i in (0, 2, 4)) + (a,)

def xy(vals):
    return tuple(int(v*S) for v in vals)


def pt(x, y):
    return (int(x*S), int(y*S))

text = C('#f8fafc')
muted = C('#94a3b8')
cyan = C('#22d3ee')
blue = C('#38bdf8')
emerald = C('#34d399')
violet = C('#a78bfa')
amber = C('#fbbf24')
orange = C('#fb923c')
slate = C('#94a3b8')

font_dir = Path('/usr/share/fonts/truetype/dejavu')
mono = str(font_dir / 'DejaVuSansMono.ttf')
mono_bold = str(font_dir / 'DejaVuSansMono-Bold.ttf')
sans = str(font_dir / 'DejaVuSans.ttf')
sans_bold = str(font_dir / 'DejaVuSans-Bold.ttf')

def F(path, size):
    return ImageFont.truetype(path, size*S)

f_tag = F(mono_bold, 15)
f_title = F(sans_bold, 39)
f_sub = F(sans, 21)
f_h = F(mono_bold, 17)
f_card = F(mono_bold, 16)
f_body = F(mono, 12)
f_small = F(mono, 10)
f_tiny = F(mono, 9)
f_layer = F(mono_bold, 13)
f_bottom_h = F(mono_bold, 20)
f_bottom_body = F(mono, 14)
f_stage_title = F(mono_bold, 18)
f_stage_sub = F(mono, 12)
f_legend = F(mono, 12)

for cx, cy, r, color in [
    (170, 90, 300, C('#38bdf8', 70)),
    (1680, 120, 360, C('#a78bfa', 55)),
    (1050, 1110, 420, C('#34d399', 42)),
]:
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay, 'RGBA')
    od.ellipse(xy((cx-r, cy-r, cx+r, cy+r)), fill=color)
    overlay = overlay.filter(ImageFilter.GaussianBlur(90*S))
    img.alpha_composite(overlay)
    draw = ImageDraw.Draw(img, 'RGBA')

def rounded_rect(x, y, w, h, fill, outline=None, width=1, radius=16):
    draw.rounded_rectangle(xy((x, y, x+w, y+h)), radius=radius*S, fill=fill, outline=outline, width=width*S if outline else 1)

def text_center(txt, cx, y, font, fill=text):
    bbox = draw.textbbox((0, 0), txt, font=font)
    tw = (bbox[2] - bbox[0]) / S
    draw.text((int((cx - tw/2)*S), int(y*S)), txt, font=font, fill=fill)

def text_left(txt, x, y, font, fill=text):
    draw.text(pt(x, y), txt, font=font, fill=fill)

def arrow_poly(points, color=C('#64748b'), width=2, arrow_len=16, arrow_w=10):
    pts = [xy(p) for p in points]
    draw.line(pts, fill=color, width=width*S, joint='curve')
    (x1, y1), (x2, y2) = points[-2], points[-1]
    ang = math.atan2(y2-y1, x2-x1)
    p1 = (x2, y2)
    p2 = (x2 - arrow_len*math.cos(ang) + arrow_w*math.sin(ang)/2, y2 - arrow_len*math.sin(ang) - arrow_w*math.cos(ang)/2)
    p3 = (x2 - arrow_len*math.cos(ang) - arrow_w*math.sin(ang)/2, y2 - arrow_len*math.sin(ang) + arrow_w*math.cos(ang)/2)
    draw.polygon([xy(p1), xy(p2), xy(p3)], fill=color)

def card(x, y, w, h, title, lines, stroke, fill, footer=None):
    shadow = Image.new('RGBA', img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, 'RGBA')
    sd.rounded_rectangle(xy((x+5, y+12, x+w+5, y+h+12)), radius=16*S, fill=C('#000000', 55))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10*S))
    img.alpha_composite(shadow)
    rounded_rect(x, y, w, h, C('#0f172a', 242), None, 1, 16)
    rounded_rect(x, y, w, h, fill, stroke, 2, 16)
    text_center(title, x+w/2, y+18, f_card, text)
    yy = y + 45
    for ln in lines:
        text_center(ln, x+w/2, yy, f_body, muted)
        yy += 19
    if footer:
        text_center(footer, x+w/2, y+h-22, f_tiny, stroke)

def pill(x, y, label, stroke, fill):
    bbox = draw.textbbox((0, 0), label, font=f_legend)
    tw = (bbox[2]-bbox[0]) / S
    rounded_rect(x, y, tw+28, 34, fill, stroke, 1, 17)
    text_left(label, x+14, y+9, f_legend, stroke)

text_left('●  OPERATIONAL WORKFLOW ARCHITECTURE', 70, 54, f_tag, cyan)
text_left('AgentRed turns scattered demand signals into ranked decisions.', 70, 86, f_title, text)
sub = 'MapReduce-style workflow for collecting job-market inputs, normalizing them, routing batches, validating signals, and producing decision-ready reports.'
for i, line_txt in enumerate(textwrap.wrap(sub, 95)):
    text_left(line_txt, 72, 152 + i*29, f_sub, C('#cbd5e1'))
rounded_rect(50, 210, 1900, 610, C('#0f172a', 120), C('#334155', 190), 1, 26)
text_left('Core demand-intelligence workflow', 84, 238, f_h, C('#cbd5e1'))

layers = [
    (80, 280, 260, 430, 'External demand sources', slate),
    (390, 280, 530, 430, 'Intake and source-of-truth layer', cyan),
    (965, 280, 230, 430, 'Routing layer', emerald),
    (1235, 280, 290, 430, 'Parallel work layer', orange),
    (1570, 280, 300, 430, 'Decision layer', violet),
]
for x, y, w, h, label, col in layers:
    rounded_rect(x, y, w, h, C('#020617', 52), C('#475569', 130), 1, 18)
    text_left(label, x+18, y+18, f_layer, col)

arrow_poly([(300, 342), (360, 342), (420, 390)], C('#64748b'), 2)
arrow_poly([(300, 432), (360, 432), (420, 404)], C('#64748b'), 2)
arrow_poly([(300, 522), (360, 522), (420, 424)], C('#64748b'), 2)
arrow_poly([(300, 612), (360, 612), (420, 444)], C('#64748b'), 2)
arrow_poly([(630, 405), (690, 405)], cyan, 2)
arrow_poly([(795, 455), (795, 500)], violet, 2)
arrow_poly([(900, 545), (985, 455)], emerald, 2)
arrow_poly([(1175, 455), (1215, 455), (1215, 388), (1265, 388)], orange, 2)
arrow_poly([(1175, 455), (1265, 515)], orange, 2)
arrow_poly([(1175, 455), (1215, 455), (1215, 638), (1265, 638)], orange, 2)
arrow_poly([(1495, 515), (1560, 515), (1560, 370), (1600, 370)], violet, 2)
arrow_poly([(1715, 410), (1715, 455)], violet, 2)
arrow_poly([(1715, 550), (1715, 595)], violet, 2)

card(110, 315, 200, 82, 'Upwork', ['EXA search', '200-400 posts'], slate, C('#1e293b', 120))
card(110, 405, 200, 82, 'Fiverr', ['EXA search', '100-200 posts'], slate, C('#1e293b', 120))
card(110, 495, 200, 82, 'Himalayas', ['free JSON API', '100-200 posts'], slate, C('#1e293b', 120))
card(110, 585, 200, 82, 'Jobicy', ['free REST API', 'remote jobs'], slate, C('#1e293b', 120))
card(420, 345, 210, 120, 'Collectors', ['ExaCollector', 'HimalayasCollector', 'JobicyCollector'], cyan, C('#083344', 120), 'collect_all()')
card(690, 345, 230, 120, 'JobPost schema', ['source, budget, skills', 'category, company, URL', 'compact mapper input'], violet, C('#4c1d95', 95))
card(690, 500, 230, 90, 'Deduplicated list', ['global job_id check', 'single source of truth'], violet, C('#4c1d95', 80))
card(985, 390, 190, 130, 'Partitioner', ['batch size 10-100', 'deterministic shuffle', 'route work packets'], emerald, C('#064e3b', 115))
card(1265, 350, 230, 75, 'Mapper batch-001', ['skills, tools, pain points'], orange, C('#7c2d12', 90), 'isolated context')
card(1265, 478, 230, 75, 'Mapper batch-002', ['budget and automation signals'], orange, C('#7c2d12', 90), 'wave controlled')
card(1265, 600, 230, 75, 'Mapper batch-N', ['DemandSignal JSON'], orange, C('#7c2d12', 90), 'parse and repair')
card(1600, 315, 230, 110, 'Reducer', ['aggregate and cluster', 'resolve contradictions', 'rank opportunity themes'], violet, C('#4c1d95', 100))
card(1600, 465, 230, 95, 'Demand score', ['volume + budget', 'automation + evidence'], amber, C('#78350f', 80))
card(1600, 600, 230, 90, 'Report outputs', ['Markdown + DOCX', 'JSON run report'], emerald, C('#064e3b', 105))

rounded_rect(50, 860, 1900, 270, C('#0f172a', 150), C('#334155', 190), 1, 26)
rounded_rect(74, 898, 14, 170, C('#38bdf8', 190), None, 1, 7)
text_left('Layer of abstraction for operational workflows', 110, 895, f_bottom_h, text)
text_left('Same control pattern: scattered inputs become a traceable workflow with status, validation, and decision output.', 110, 930, f_bottom_body, muted)

stage_y = 975
stage_w = 250
stage_h = 96
xs = [110, 420, 730, 1040, 1350, 1660]
stages = [
    ('1. Intake', 'raw posts, files, forms', cyan),
    ('2. Normalize', 'schema + source of truth', violet),
    ('3. Route', 'batch, assign, track', emerald),
    ('4. Execute', 'focused work packets', orange),
    ('5. Synthesize', 'merge, score, verify', amber),
    ('6. Report', 'dashboard, brief, archive', blue),
]
for i in range(len(xs)-1):
    arrow_poly([(xs[i]+stage_w, stage_y+stage_h/2), (xs[i+1]-24, stage_y+stage_h/2)], C('#64748b'), 2)
for x, (title, subtxt, col) in zip(xs, stages):
    rounded_rect(x, stage_y, stage_w, stage_h, C('#0f172a', 235), col, 2, 16)
    text_center(title, x+stage_w/2, stage_y+23, f_stage_title, text)
    text_center(subtxt, x+stage_w/2, stage_y+58, f_stage_sub, muted)
text_left('Operational translation: allocation data, store confirmations, campaign entries, photo proofs, and BI exports can use the same intake - tracker - gate - report pattern.', 110, 1098, f_legend, C('#94a3b8'))

pill(70, 1160, 'workflow/service', cyan, C('#083344', 120))
pill(270, 1160, 'data/schema', violet, C('#4c1d95', 90))
pill(435, 1160, 'execution', orange, C('#7c2d12', 90))
pill(585, 1160, 'decision', amber, C('#78350f', 80))
text_left('AgentRed architecture diagram - standalone PNG generated from repo-grounded system structure.', 1115, 1169, f_legend, C('#64748b'))

img = img.convert('RGB').resize((W, H), Image.Resampling.LANCZOS)
OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT, quality=95, optimize=True)
print(str(OUT))
print(OUT.stat().st_size)
