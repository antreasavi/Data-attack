# pseudo-decompiled atomic_write.pyc

def <module>():   # line 1
    """Atomic file write so a crash mid-write can never leave a partial file
that the GUI thread would then read."""
    L1: __doc__ = 'Atomic file write so a crash mid-write can never leave a partial file\nthat the GUI thread would then read.'
    L3: os = import os
    L4: Path = import pathlib.Path ; import pathlib
    L7: write_text = func<code write_text> ; return None

    def write_text(path, text):   # line 7
        L8: tmp = path.with_suffix((path.suffix + '.tmp'))
        L9: with open(tmp, 'w', encoding='utf-8', newline='\n'): ; f = <as open(tmp, 'w', encoding='utf-8', newline='\n')>
        L10: f.write(text)
        L11: f.flush()
        L12: os.fsync(f.fileno())
        L9: None(None, None) ; goto 304 ; except-handler: ; <WITH_EXCEPT_START > ; if <exc>: goto 296 ; reraise ; pop_except ; reraise ; @296: ; ? ; pop_except ; <with-exit> ; ?
        L13: @304: ; os.replace(tmp, path) ; return None