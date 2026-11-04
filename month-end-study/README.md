# Month-end close study

Do the MarketWatch products move consistently around the closes on the last business day of each month?

For every weekday on record it measures each product in the 30 minutes before and after three reference times: the London 4pm fix (16:00 London), the UK close (16:30 London) and the US close (16:00 New York). Month-end days are compared with every other weekday.

## Run

```powershell
python extract.py   # ~5 minutes; reads only the hour around each close from C:\SierraChart\Data
python analyze.py   # statistics -> output\summary.json and output\dash\*.json
python trade_study.py   # trade plans for the Promising tests -> output\trade\plans.json, grid.json, trades.json
```

`extract.py --roots 6B ES` limits the run to a few products. `--data-dir` (or `SIERRA_DATA_DIR`) points at another Sierra data folder.

The reader opens `.scid` files read-only, shares read/write/delete with Sierra and runs at background I/O priority, as MarketWatch does. It never writes to Sierra's folders.

## Outputs

- `output/events.csv`: every window (month-end and normal days) with prices, volume and the contract used.
- `output/dash/stats.json`: one row per product, reference time and window, with its verdict.
- `output/dash/events.json`, `paths.json`, `coverage.json`: the dashboard's other tables.
- `output/trade/plans.json`: each Promising test replayed as a trade after costs (1 tick of slippage plus $4.50 per round turn): a second check, the best entry, exit and tick stop, and out-of-sample results. `grid.json` holds every entry/exit/stop tried, `trades.json` the chosen plan at each month-end.

The dashboard is the "Month-end close study" artifact. After a rerun, ask Claude to upload the new `output/dash` and `output/trade` files to it.
