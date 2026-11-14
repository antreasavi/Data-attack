import struct, sys, os, zlib
exe, out = sys.argv[1], sys.argv[2]
data = open(exe, 'rb').read()
MAGIC = b'MEI\x0c\x0b\x0a\x0b\x0e'
pos = data.rfind(MAGIC)
cookie_fmt = '!8sIIii64s'
magic, pkg_len, toc_off, toc_len, pyver, pylib = struct.unpack(cookie_fmt, data[pos:pos + struct.calcsize(cookie_fmt)])
tail = pos + struct.calcsize(cookie_fmt)
start = tail - pkg_len
print('pyver', pyver, 'lib', pylib.rstrip(b'\0'), 'pkg start', start, 'len', pkg_len)
toc = data[start + toc_off:start + toc_off + toc_len]
p = 0
entries = []
while p < len(toc):
    esz, doff, dlen, ulen, cflag, tc = struct.unpack('!IIIIBc', toc[p:p + 18])
    name = toc[p + 18:p + esz].rstrip(b'\0').decode('utf8', 'replace')
    entries.append((name, doff, dlen, ulen, cflag, tc.decode()))
    p += esz
with open(os.path.join(out, '_toc.txt'), 'w', encoding='utf8') as f:
    for e in entries:
        f.write(f'{e[5]}  {e[3]:>10}  {e[0]}\n')
for name, doff, dlen, ulen, cflag, tc in entries:
    blob = data[start + doff:start + doff + dlen]
    if cflag:
        blob = zlib.decompress(blob)
    safe = name.replace('..', '__').lstrip('/').lstrip(chr(92))
    if tc in ('s', 'm', 'M'):
        safe += '.code'
    dst = os.path.join(out, safe)
    d = os.path.dirname(dst)
    if d:
        os.makedirs(d, exist_ok=True)
    open(dst, 'wb').write(blob)
print(len(entries), 'entries')
