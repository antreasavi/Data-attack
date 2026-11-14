import struct, sys, os, zlib, marshal
pyz, out = sys.argv[1], sys.argv[2]
data = open(pyz, 'rb').read()
assert data[:4] == b'PYZ\0', data[:4]
pyc_magic = data[4:8]
toc_off = struct.unpack('!i', data[8:12])[0]
toc = marshal.loads(data[toc_off:])
if isinstance(toc, list):
    toc = dict(toc)
names = sorted(toc)
with open(os.path.join(out, '_pyz_toc.txt'), 'w', encoding='utf8') as f:
    for n in names:
        f.write(f'{n}  {toc[n]}\n')
header = pyc_magic + b'\0' * 12
for n in names:
    entry = toc[n]
    typ, off, ln = entry[0], entry[1], entry[2]
    try:
        blob = zlib.decompress(data[off:off + ln])
    except Exception as e:
        print('FAIL', n, entry, e); continue
    path = os.path.join(out, *n.split('.'))
    if typ in (1,):  # package
        path = os.path.join(path, '__init__')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path + '.pyc', 'wb').write(header + blob)
print('magic', pyc_magic.hex(), len(names), 'modules')
