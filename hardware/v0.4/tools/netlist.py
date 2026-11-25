"""Читання нетлиста KiCad (kicad-cli sch export netlist --format kicadsexpr)."""
import re

def sexpr(text):
    toks = re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+', text)
    stack = [[]]
    for t in toks:
        if t == "(":
            stack.append([])
        elif t == ")":
            x = stack.pop(); stack[-1].append(x)
        else:
            stack[-1].append(t[1:-1].replace('\\"', '"') if t.startswith('"') else t)
    return stack[0][0]

def find(node, key):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == key]

def val(node, key, default=None):
    f = find(node, key)
    return f[0][1] if f and len(f[0]) > 1 else default

def load(path):
    root = sexpr(open(path, encoding="utf-8").read())
    comps = {}
    for c in find(find(root, "components")[0], "comp"):
        ref = val(c, "ref")
        ts = find(c, "tstamps")
        fields = {}
        for fs in find(c, "fields"):
            for f in find(fs, "field"):
                nm = val(f, "name")
                txt = [x for x in f[1:] if isinstance(x, str)]
                if nm: fields[nm] = txt[-1] if txt else ""
        comps[ref] = dict(value=val(c, "value"), footprint=val(c, "footprint", ""),
                          uuid=ts[0][1] if ts else None, fields=fields)
    nets = {}
    for n in find(find(root, "nets")[0], "net"):
        name = val(n, "name")
        nets[name] = [(val(x, "ref"), val(x, "pin")) for x in find(n, "node")]
    return comps, nets

if __name__ == "__main__":
    import sys
    c, n = load(sys.argv[1])
    print(len(c), "comps", len(n), "nets")
