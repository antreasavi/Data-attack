"""Start the Fed STIR scenario tool:  python -m stirtool  (from the rates-tools folder)."""
import argparse
import json
import os
import time
import webbrowser

from .engine import Engine
from .server import serve

DEFAULTS = {'data_dir': r'C:\SierraChart\SierraChartInstance_5\Data', 'chartbook': 'STERS .Cht', 'port': 8791}


def load_config():
    cfg = dict(DEFAULTS)
    path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            cfg.update(json.load(f))
    return cfg


def main():
    cfg = load_config()
    ap = argparse.ArgumentParser(description='Fed STIR scenario tool (ZQ / SR3 from Sierra Chart)')
    ap.add_argument('--data-dir', default=cfg['data_dir'])
    ap.add_argument('--chartbook', default=cfg['chartbook'])
    ap.add_argument('--port', type=int, default=cfg['port'])
    ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args()
    engine = Engine(a.data_dir, a.chartbook)
    engine.start()
    serve(engine, port=a.port)
    url = f'http://127.0.0.1:{a.port}/'
    print(f'Fed STIR tool running at {url}  (Sierra: {a.data_dir} / {a.chartbook})  Ctrl+C to stop')
    if not a.no_browser:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        engine.stop()


if __name__ == '__main__':
    main()
