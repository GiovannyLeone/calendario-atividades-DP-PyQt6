"""Gera as imagens PNG dos diagramas de classes a partir dos blocos Mermaid de docs/diagramas.md.

Usa o Graphviz (comando ``dot``), que só desenha as seções (atributos/métodos) com conteúdo.
Uso:  python docs/gerar_diagramas.py      (requer Graphviz instalado: https://graphviz.org/download/)
"""
import html
import os
import re
import subprocess
import tempfile

DOCS = os.path.dirname(os.path.abspath(__file__))
src_md = os.path.join(DOCS, "diagramas.md")
OUT = os.path.join(DOCS, "img")
text_md = open(src_md, encoding="utf-8").read()
names = re.findall(r"!\[[^\]]*\]\(img/([^)]+)\.png\)", text_md)
blocks = re.findall(r"```mermaid\n(.*?)```", text_md, re.S)
assert len(blocks) == len(names), "cada bloco Mermaid precisa de uma imagem correspondente"
os.makedirs(OUT, exist_ok=True)
E = lambda t: html.escape(t, quote=False)

def parse(text):
    text = re.sub(r"^---.*?---\n", "", text, flags=re.S)
    classes, order, rels = {}, [], []
    cur = None
    def get(n):
        if n not in classes: classes[n] = {"stereo": None, "attrs": [], "meths": []}; order.append(n)
        return classes[n]
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("classDiagram") or line.startswith("direction"): continue
        m = re.match(r"class (\w+) \{$", line)
        if m: cur = get(m.group(1)); continue
        if line == "}": cur = None; continue
        if cur is not None:
            s = re.match(r"<<(.+)>>$", line)
            if s: cur["stereo"] = s.group(1); continue
            (cur["meths"] if "(" in line else cur["attrs"]).append(line); continue
        m = re.match(r"(\w+) (<\|--|<\|\.\.|o-->|\*-->|-->|\.\.>) (\w+)(?: : (.+))?$", line)
        if m: get(m.group(1)); get(m.group(3)); rels.append(m.groups()); continue
        raise SystemExit("linha não reconhecida: " + line)
    return classes, order, rels

def label(name, c, hdr, alt):
    rows = []
    title = f"<B>{E(name)}</B>"
    if c["stereo"]: title = f"<FONT POINT-SIZE='9' COLOR='#555555'>«{E(c['stereo'])}»</FONT><BR/>" + title
    rows.append(f"<TR><TD BGCOLOR='{hdr}' ALIGN='CENTER'>{title}</TD></TR>")
    def cell(items):
        out = []
        for it in items:
            it = it.strip()
            ital = it.endswith("*"); it = it.rstrip("*")
            t = E(it); t = f"<I>{t}</I>" if ital else t
            out.append(f"<TR><TD ALIGN='LEFT' BORDER='0'>{t}</TD></TR>")
        return "<TABLE BORDER='0' CELLBORDER='0' CELLSPACING='0' CELLPADDING='1'>" + "".join(out) + "</TABLE>"
    for key in ("attrs", "meths"):          # só desenha a seção quando há conteúdo
        if c[key]: rows.append(f"<TR><TD ALIGN='LEFT' BGCOLOR='{alt}'>{cell(c[key])}</TD></TR>")
    return "<<TABLE BORDER='1' COLOR='#5B6B8C' CELLBORDER='1' CELLSPACING='0' CELLPADDING='5'>" + "".join(rows) + "</TABLE>>"

STYLE = {"<|--": ("onormal", "none", "solid"), "<|..": ("onormal", "none", "dashed"),
         "o-->": ("vee", "odiamond", "solid"), "*-->": ("vee", "diamond", "solid"),
         "-->": ("vee", "none", "solid"), "..>": ("vee", "none", "dashed")}
for n, b in zip(names, blocks):
    classes, order, rels = parse(b)
    d = ["digraph G {", "rankdir=BT;", "nodesep=0.45; ranksep=0.7; splines=true; pad=0.25; bgcolor=white;",
         "node [shape=plain, fontname='DejaVu Sans', fontsize=10];".replace("'", '"'),
         "edge [fontname=\"DejaVu Sans\", fontsize=9, color=\"#44506B\"];"]
    for name in order:
        c = classes[name]
        abstract = c["stereo"] in ("abstract", "interface")
        hdr = "#E3EAF8" if abstract else "#D4E4FA"
        alt = "#FFFFFF"
        d.append(f'{name} [label={label(name, c, hdr, alt)}];')
    for a, op, b2, lab in rels:
        head, tail, style = STYLE[op]
        l = f', label=" {lab}"' if lab else ""
        if op in ("<|--", "<|.."):  # b2 herda/implementa a
            d.append(f'{b2} -> {a} [arrowhead={head}, style={style}{l}];')
        else:                       # a -> b2, com losango na origem quando agregação/composição
            d.append(f'{a} -> {b2} [arrowhead={head}, arrowtail={tail}, dir=both, style={style}{l}];')
    d.append("}")
    dot = "\n".join(d)
    with tempfile.NamedTemporaryFile("w", suffix=".dot", delete=False, encoding="utf-8") as tmp:
        tmp.write(dot)
    subprocess.run(["dot", "-Tpng", "-Gdpi=140", tmp.name, "-o", os.path.join(OUT, f"{n}.png")], check=True)
    os.unlink(tmp.name)
    print(n, "ok", len(order), "classes")
