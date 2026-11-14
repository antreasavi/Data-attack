"""Always-on-top strip: what is priced now, what moved vs the strip, and the scenario's best targets.

Reads the running tool's state from http://127.0.0.1:<port>/api/state once a second.
Drag with the left mouse button; right-click for the menu.
"""
import json
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser

BG, INK, SEC, MUTED = '#0d0d0d', '#f0efec', '#c3c2b7', '#898781'
NOW, SCN, GOOD, WARN, BAD = '#3987e5', '#d95926', '#0ca30c', '#fab219', '#d03b3b'
FONT = ('Consolas', 11, 'bold')
SMALL = ('Consolas', 10)


def sgn(v, d=1):
    if v is None:
        return '-'
    return ('+' if v > 0 else '-' if v < 0 else '±') + f'{abs(v):.{d}f}'


class Strip:
    def __init__(self, port=8791, meetings=6):
        self.url = f'http://127.0.0.1:{port}/'
        self.n_meet = meetings
        self.state, self.err = None, None
        self.root = tk.Tk()
        self.root.title('Fed STIR strip')
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg=BG, highlightthickness=1, highlightbackground='#333333')
        self.root.geometry('+40+40')
        self.lines = []
        for _ in range(3):
            t = tk.Text(self.root, height=1, width=128, bg=BG, fg=INK, bd=0, highlightthickness=0,
                        font=FONT, cursor='fleur', padx=8, pady=1)
            for tag, col in (('ink', INK), ('sec', SEC), ('mut', MUTED), ('now', NOW), ('scn', SCN),
                             ('good', GOOD), ('warn', WARN), ('bad', BAD)):
                t.tag_configure(tag, foreground=col)
            t.tag_configure('small', font=SMALL)
            t.pack(fill='x')
            self.lines.append(t)
        self.menu = tk.Menu(self.root, tearoff=0, bg='#232321', fg=INK)
        self.menu.add_command(label='Open web page', command=lambda: webbrowser.open(self.url))
        self.menu.add_command(label='Toggle always on top', command=self._toggle_top)
        self.menu.add_separator()
        self.menu.add_command(label='Close strip', command=self.root.destroy)
        for w in [self.root] + self.lines:
            w.bind('<ButtonPress-1>', self._start_drag)
            w.bind('<B1-Motion>', self._drag)
            w.bind('<Button-3>', lambda e: self.menu.tk_popup(e.x_root, e.y_root))
            w.bind('<Double-Button-1>', lambda e: webbrowser.open(self.url))
        threading.Thread(target=self._poll, daemon=True).start()
        self.root.after(300, self._refresh)

    # ---- window behaviour --------------------------------------------------------------
    def _toggle_top(self):
        self.root.attributes('-topmost', not self.root.attributes('-topmost'))

    def _start_drag(self, e):
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _drag(self, e):
        self.root.geometry(f'+{e.x_root - self._dx}+{e.y_root - self._dy}')

    # ---- data --------------------------------------------------------------------------
    def _poll(self):
        while True:
            try:
                with urllib.request.urlopen(self.url + 'api/state', timeout=3) as r:
                    s = json.loads(r.read())
                if s.get('meetings') is not None:
                    self.state, self.err = s, None
            except Exception as exc:
                self.err = str(exc)
            time.sleep(1)

    def _write(self, i, parts):
        t = self.lines[i]
        t.configure(state='normal')
        t.delete('1.0', 'end')
        for text, tag in parts:
            t.insert('end', text, tag)
        t.configure(state='disabled')

    def _refresh(self):
        s = self.state
        if s is None:
            self._write(0, [('FED STIR  ', 'ink'), ('waiting for the tool on ' + self.url, 'warn')])
            self._write(1, [(self.err or '', 'mut')])
            self._write(2, [('', 'mut')])
        else:
            self._render(s)
        self.root.after(1000, self._refresh)

    def _render(self, s):
        feed = s['feed']['status']
        dot = {'live': ('● LIVE ', 'good'), 'quiet': ('● QUIET', 'warn'), 'closed': ('● CLOSED', 'mut')}.get(feed, ('● NO DATA', 'bad'))
        if self.err:
            dot = ('● OFFLINE', 'bad')
        line = [(dot[0] + ' ', dot[1]), (f"EFFR {s['rates']['effr']:.2f}  ", 'mut')]
        for m in s['meetings'][:self.n_meet]:
            mon = time.strftime('%b', time.strptime(m['date'], '%Y-%m-%d')).upper()
            line += [(f"{mon}{m['date'][2:4]} ", 'sec'), (f"{sgn(m['priced_bp'])}", 'ink'),
                     (f"({sgn(m['change_bp'])}) ", 'mut')]
        self._write(0, line)

        lagged = [c for c in s['contracts'] if c.get('lag_ticks') is not None and not c['stale']]
        lagged.sort(key=lambda c: -abs(c['lag_ticks']))
        line = [('LAG vs strip  ', 'mut')]
        for c in lagged[:4]:
            word = 'rich' if c['lag_ticks'] > 0 else 'cheap'
            line += [(f"{c['symbol']} ", 'ink'), (f"{sgn(c['lag_ticks'])}t {word}   ", 'bad' if c['lag_ticks'] > 0 else 'now')]
        stale = [c['symbol'] for c in s['contracts'] if c['stale']]
        if stale:
            line += [('stale: ' + ' '.join(stale), 'warn')]
        self._write(1, line)

        sc = s['scenario']
        if not sc['active']:
            self._write(2, [('SCENARIO  ', 'mut'), ('none set: pick one on the web page (double-click here)', 'mut')])
            return
        edits = ', '.join(f"{time.strftime('%b', time.strptime(d, '%Y-%m-%d'))} {sgn(v, 0)}" for d, v in sc['edits'].items())
        mode = {'whole': 'whole', 'pull': 'pull-fwd', 'fade': f"fade {sc['fade']:.2f}"}[sc['mode']]
        line = [('SCN ', 'scn'), (f'{edits} ({mode}): ', 'sec')]
        best = []
        for prod in ('ZQ', 'SR3'):
            cs = sorted((c for c in s['contracts'] if c['product'] == prod and c.get('scn_ticks') is not None),
                        key=lambda c: -abs(c['scn_ticks']))
            best += cs[:2]
        for c in best:
            dp = 4 if c['tick'] < 0.005 else 3
            line += [(f"{c['symbol']} ", 'ink'), (f"{c['target']:.{dp}f} ", 'scn'), (f"{sgn(c['scn_ticks'], 0)}t  ", 'sec')]
        self._write(2, line)

    def run(self):
        self.root.mainloop()


def main(port=8791):
    Strip(port).run()


if __name__ == '__main__':
    main()
