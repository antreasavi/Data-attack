# pseudo-decompiled fetch_boe.pyc

def <module>():   # line 1
    L1: os = import os
    L2: sys = import sys
    L4: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    L6: boe_ois = import boe_ois
    L7: run_forever = import ratecore.run_forever ; run_loop = import ratecore.run_loop ; import ratecore
    L9: PREFIX = 'BOE'
    L12: start = func<code start>
    L16: if not (__name__ == '__main__'): goto 300
    L17: run_forever(PREFIX, boe_ois.fetch) ; return None
    L16: @300: ; return None

    def start(stop):   # line 12
        L13: run_loop(PREFIX, boe_ois.fetch, stop) ; return None