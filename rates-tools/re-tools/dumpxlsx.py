import sys, os, re
import xml.etree.ElementTree as ET

root = sys.argv[1]  # extracted xlsx dir
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
sst = []
t = ET.parse(os.path.join(root, 'xl/sharedStrings.xml'))
for si in t.getroot().findall('m:si', NS):
    sst.append(''.join(x.text or '' for x in si.iter('{%s}t' % NS['m'])))


def col2n(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n


def n2col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def shift(formula, dr, dc):
    def rep(m):
        cabs, col, rabs, row = m.group(1), m.group(2), m.group(3), m.group(4)
        if not cabs:
            col = n2col(col2n(col) + dc)
        if not rabs:
            row = str(int(row) + dr)
        return f'{cabs}{col}{rabs}{row}'
    return re.sub(r'(?<![A-Za-z_"])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![\d(])', rep, formula)


for sheet, name in (('sheet1.xml', 'Sheet1'), ('sheet2.xml', 'Spread')):
    print(f'\n===== {name}')
    tree = ET.parse(os.path.join(root, 'xl/worksheets', sheet)).getroot()
    shared = {}
    for c in tree.iter('{%s}c' % NS['m']):
        ref = c.get('r')
        typ = c.get('t')
        f = c.find('m:f', NS)
        v = c.find('m:v', NS)
        val = v.text if v is not None else None
        if typ == 's' and val is not None:
            val = sst[int(val)]
        ftxt = None
        if f is not None:
            if f.get('t') == 'shared':
                si = f.get('si')
                if f.text:
                    shared[si] = (ref, f.text)
                    ftxt = f.text
                else:
                    oref, otxt = shared[si]
                    m1 = re.match(r'([A-Z]+)(\d+)', oref)
                    m2 = re.match(r'([A-Z]+)(\d+)', ref)
                    ftxt = shift(otxt, int(m2.group(2)) - int(m1.group(2)), col2n(m2.group(1)) - col2n(m1.group(1)))
            else:
                ftxt = f.text
                if f.get('t') == 'array':
                    ftxt = '{array ' + str(f.get('ref')) + '} ' + str(ftxt)
        if ftxt is None and val is None:
            continue
        if ftxt:
            print(f'{ref:>6}  ={ftxt}   ->  {val}')
        else:
            print(f'{ref:>6}  {val}')
