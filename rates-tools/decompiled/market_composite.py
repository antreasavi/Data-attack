# pseudo-decompiled market_composite.pyc

def <module>():   # line 1
    """Free dated-market observations and an auditable quote-age weighted composite.

This blends comparable annualized compounded period rates. It does not claim
to extract policy probabilities or eliminate futures/OIS basis and model risk."""
    L1: __doc__ = 'Free dated-market observations and an auditable quote-age weighted composite.\n\nThis blends comparable annualized compounded period rates. It does not claim\nto extract policy probabilities or eliminate futures/OIS basis and model risk.\n'
    L6: csv = import csv
    L7: json = import json
    L8: math = import math
    L9: deepcopy = import copy.deepcopy ; import copy
    L10: datetime = import datetime.datetime ; timezone = import datetime.timezone ; import datetime
    L12: write_text = import atomic_write.write_text ; import atomic_write
    L13: data_dir = import paths.data_dir ; import paths
    L15: UTC = timezone.utc
    L16: HALF_LIFE_HOURS = 24.0
    L17: MAX_QUOTE_HOURS = 72.0
    L18: ICE = {'BOE': (30027, 30177, 83047279), 'ECB': (29802, 30019, 83046794)}
    L24: cached_get = func<code cached_get>
    L49: expiry_periods = func<code expiry_periods>
    L66: ice_observations = func<code ice_observations>
    L95: blend = func<code blend>
    L121: apply_composite = func<code apply_composite>
    L171: reference_check = func<code reference_check> ; return None

    def cached_get(http, name, url, now, ttl, is_json):   # line 24
        L25: path = (data_dir() / (('market_' + name) + '.json'))
        L26: cached = None
        L28: cached = json.loads(path.read_text(encoding='utf8'))
        L29: if not (cached['url'] != url): goto 164
        L30: cached = None ; goto 290
        L31: @164: ; if not (0 <= (now - datetime.fromisoformat(cached['fetched_at'])).total_seconds()): goto 282 ; if not ((now - datetime.fromisoformat(cached['fetched_at'])).total_seconds() < ttl): goto 290 ; goto 286 ; @282: ; ? ; goto 290
        L32: @286: ; return cached ; @290: ; goto 366 ; except-handler:
        L33: except (OSError, ValueError, KeyError, TypeError)? ; if not match((OSError, ValueError, KeyError, TypeError)): goto 358 ; <exc>
        L34: cached = None ; pop_except ; goto 366
        L33: @358: ; reraise ; pop_except ; reraise
        L35: @366:
        L36: response = http.get(url, timeout=(5, 15))
        L37: response.raise_for_status()
        L38: if not is_json: goto 498 ; goto 510 ; @498: ; @510: ; payload = response.text
        L39: record = {'url': url, 'fetched_at': now.isoformat(), 'payload': payload}
        L40: write_text(path, json.dumps(record, allow_nan=False))
        L41: return record ; except-handler:
        L42: except Exception? ; if not match(Exception): goto 740 ; exc = <exc>
        L43: if not cached: goto 730
        L45: pop_except ; exc = None ; del exc ; return response.json()
        L46: @730: ; raise  ; exc = None ; del exc ; reraise
        L42: @740: ; reraise ; pop_except ; reraise

    def expiry_periods(text):   # line 49
        L50: rows = []
        L51: for-next iter(csv.DictReader(text.splitlines())) (exhausted->346) ; row = <item>
        L52: symbol = row['CONTRACT SYMBOL']
        L53: if not symbol.startswith('="'): goto 208 ; if not symbol.endswith('"'): goto 208
        L54: symbol = symbol[2:-1]
        L55: @208: ; end = datetime.strptime(row['FSD'], '%m/%d/%Y').date()
        L56: rows.append((end, symbol)) ; goto 84
        L57: @346: ; rows.sort()
        L58: if not (func<code <setcomp>>(iter(rows)()) != len(rows)): goto 500
        L59: raise ValueError('Duplicate ICE expiry dates')
        L62: @500:
        L62: return iter(enumerate(rows))()

        def expiry_periods.<locals>.<setcomp>(.0):   # line 58
            L58: for-next .0 (exhausted->22) ; end = <item>[0] ; _ = <item>[1] ; set-add end ; goto 6 ; @22: ; return .0

        def expiry_periods.<locals>.<dictcomp>(.0):   # line 62
            L62: for-next .0 (exhausted->150)
            L63: i = <item>[0] ; end = <item>[1][0] ; symbol = <item>[1][1] ; if not (i > 0): goto 8
            L62: @64:
            L63: map-add symbol: (rows[(i - 1)][0].isoformat(), end.isoformat()) ; goto 8 ; @150: ; return .0

    def ice_observations(rows, periods, now):   # line 66
        L67: rejected = [] ; observations = []
        L68: if isinstance(rows, list): goto 82
        L69: raise ValueError('Invalid ICE contract payload')
        L70: @82: ; for-next iter(rows) (exhausted->1048) ; row = <item>
        L72: symbol = row['marketStrip']
        L73: if not (symbol not in periods): goto 148
        L74: raise ValueError('No complete published accrual interval')
        L75: @148: ; price = float(row['lastPrice'])
        L76: if not math.isfinite(price): goto 260 ; if not (50 < price): goto 258 ; if (price < 150): goto 290 ; goto 260 ; @258: ; iter(rows)
        L77: @260: ; raise ValueError('Missing/invalid price')
        L78: @290: ; stamp = datetime.strptime(row['lastTime'], '%m/%d/%Y %I:%M %p GMT').replace(tzinfo=UTC)
        L79: age = ((now - stamp).total_seconds() / 3600)
        L80: if not (0 <= age): goto 484 ; if (age <= MAX_QUOTE_HOURS): goto 516 ; goto 486 ; @484: ; ?
        L81: @486: ; raise ValueError('Quote stale or future dated')
        L82: @516: ; [row.get('volume') or ...] (else goto 572) ; @572: ; volume = float(0)
        L83: if not math.isfinite(volume): goto 640 ; if not (volume <= 0): goto 670
        L84: @640: ; raise ValueError('No reported trading volume')
        L85: @670: ; start = periods[symbol][0] ; end = periods[symbol][1]
        L89: if not (volume >= 10): goto 832 ; goto 834 ; @832: ; @834:
        L86: 'ICE'({'source': 'ICE', 'upstream': str(row['marketId']), 'instrument': symbol, 'contract': start, 'start': end, 'end': (100 - price), 'rate_percent': stamp.isoformat(), 'quote_time': 'last_trade', 'time_precision': age, 'age_hours': 1.0, 'quality_weight': 0.25, 'volume': volume, 'kind': 'delayed_futures_last_trade'}) ; goto 86 ; except-handler:
        L90: except (KeyError, TypeError, ValueError)? ; if not match((KeyError, TypeError, ValueError)): goto 1040 ; exc = <exc>
        L91: rejected.append({'contract': row.get('marketStrip'), 'reason': str(exc)}) ; pop_except ; exc = None ; del exc ; goto 86 ; exc = None ; del exc ; reraise
        L90: @1040: ; reraise ; pop_except ; reraise
        L92: @1048: ; return (observations, rejected)

    def blend(inputs):   # line 95
        """One observation per upstream, identical period, deterministic age weights."""
        L97: if inputs: goto 36
        L98: raise ValueError('No composite inputs')
        L99: @36: ; if not (func<code <setcomp>>(iter(inputs)()) != 1): goto 124
        L100: raise ValueError('Mismatched accrual intervals')
        L101: @124: ; chosen = {}
        L102: for-next iter(inputs) (exhausted->494) ; row = <item>
        L103: quality = row['quality_weight'] ; age = row['age_hours'] ; rate = row['rate_percent']
        L104: if not func<code <genexpr>>(iter((rate, age, quality))()): goto 294 ; if (age < 0): goto 294 ; if (age > 168): goto 294 ; if not (0 < quality): goto 292 ; if (quality <= 1): goto 324 ; goto 294 ; @292: ; all
        L105: @294: ; raise ValueError('Invalid composite input')
        L106: @324: ; weight = (quality * (2 ** ((-age) / HALF_LIFE_HOURS)))
        L107: previous = chosen.get(row['upstream'])
        L108: if previous is None: goto 440 ; if not (weight > previous['raw_weight']): goto 492
        L109: @440: ; chosen[row['upstream']] = dict(row, raw_weight=weight) ; @492: ; goto 132
        L110: @494: ; values = list(chosen.values())
        L111: total = func<code <genexpr>>(iter(values)())
        L112: for-next iter(values) (exhausted->648) ; row = <item>
        L113: row['weight'] = (row['raw_weight'] / total) ; goto 614
        L114: @648: ; @682: ; mean = func<code <genexpr>>(iter(values)())
        L115: spread = ((min - func<code <genexpr>>(iter(values)())) * 100)
        L118: @856: ; if not (len(values) > 1): goto 892 ; goto 894 ; @892:
        L116: @894: ; return {'rate_percent': values, 'inputs': len(values), 'source_count': spread, 'spread_bps': (spread > 2.0), 'disagreement': 'age_weighted_composite', 'status': 'single_source_estimate'}

        def blend.<locals>.<setcomp>(.0):   # line 99
            L99: for-next .0 (exhausted->44) ; r = <item> ; set-add (r['start'], r['end']) ; goto 6 ; @44: ; return .0

        def blend.<locals>.<genexpr>(.0):   # line 104
            L104: ? ; for-next .0 (exhausted->58) ; v = <item> ; (yield math.isfinite(v)) ; goto 8 ; @58: ; return None

        def blend.<locals>.<genexpr>(.0):   # line 111
            L111: ? ; for-next .0 (exhausted->34) ; r = <item> ; (yield r['raw_weight']) ; goto 8 ; @34: ; return None

        def blend.<locals>.<genexpr>(.0):   # line 114
            L114: ? ; for-next .0 (exhausted->52) ; r = <item> ; (yield (r['rate_percent'] * r['weight'])) ; goto 8 ; @52: ; return None

        def blend.<locals>.<genexpr>(.0):   # line 115
            L115: ? ; for-next .0 (exhausted->34) ; r = <item> ; (yield r['rate_percent']) ; goto 8 ; @34: ; return None

        def blend.<locals>.<genexpr>(.0):   # line 115
            L115: ? ; for-next .0 (exhausted->34) ; r = <item> ; (yield r['rate_percent']) ; goto 8 ; @34: ; return None

    def apply_composite(http, snapshot, now):   # line 121
        L122: snapshot = deepcopy(snapshot)
        L123: [now or ...] (else goto 86) ; @86: ; now = datetime.now(UTC)
        L124: bank = snapshot['bank']
        L125: feeds = [] ; rejected = [] ; observations = []
        L126: if not (bank in ICE): goto 746 ; if not snapshot['meetings']: goto 746
        L127: product = ICE[bank][0] ; hub = ICE[bank][1] ; spec = ICE[bank][2]
        L129: quotes = cached_get(http, (bank.lower() + '_ice_quotes'), f"https://www.ice.com/marketdata/api/productguide/charting/contract-data?productId={product}&hubId={hub}", now, 240)
        L131: expiry = cached_get(http, (bank.lower() + '_ice_expiry'), f"https://www.ice.com/api/productguide/spec/{spec}/expiry/csv", now, 86400, is_json=False)
        L133: if not ((now - datetime.fromisoformat(expiry['fetched_at'])).total_seconds() > 604800): goto 506
        L134: raise ValueError('Expiry calendar cache too old')
        L135: @506: ; observations = ice_observations(quotes['payload'], expiry_periods(expiry['payload']), now)[0] ; rejected = ice_observations(quotes['payload'], expiry_periods(expiry['payload']), now)[1]
        L136: feeds = iter((quotes, expiry))() ; goto 746 ; except-handler:
        L137: except Exception? ; if not match(Exception): goto 738 ; exc = <exc>
        L138: rejected.append({'source': 'ICE', 'reason': str(exc)}) ; pop_except ; exc = None ; del exc ; goto 746 ; exc = None ; del exc ; reraise
        L137: @738: ; reraise ; pop_except ; reraise
        L141: @746: ; anchor_time = datetime.fromisoformat(snapshot['asof']).replace(tzinfo=UTC)
        L142: age = ((now - anchor_time).total_seconds() / 3600)
        L143: matched = 0
        L144: for-next iter(snapshot['meetings']) (exhausted->1242) ; meeting = <item>
        L145: original = meeting['rate_percent']
        L146: anchor = {'source': 'Eurex clearing curve', 'upstream': 'Eurex', 'instrument': snapshot['benchmark'], 'start': meeting['start'], 'end': meeting['end'], 'rate_percent': original, 'quote_time': None, 'asof': snapshot['asof'], 'age_anchor': anchor_time.isoformat(), 'time_precision': 'date_only_conservative_midnight', 'age_hours': age, 'quality_weight': 0.5, 'kind': 'fitted_ois_period_forward'}
        L151: eligible = iter(observations)()
        L152: result = blend(([anchor] + eligible))
        L153: meeting['eurex_rate_percent'] = original
        L154: meeting['rate_percent'] = result['rate_percent']
        L155: meeting['change_bps'] = ((result['rate_percent'] - snapshot['base_percent']) * 100)
        L156: meeting['composite'] = result
        L157: matched = (matched += (result['source_count'] > 1)) ; goto 920
        L158: @1242:
        L158: snapshot['composite'] = {'updated_at': now.isoformat(), 'blended_meetings': matched, 'feeds': feeds, 'rejected': rejected, 'half_life_hours': HALF_LIFE_HOURS, 'curve_quality_weight': 0.5, 'trade_quality_weight': 1.0, 'thin_trade_quality_weight': 0.25, 'thin_trade_volume_threshold': 10, 'max_trade_age_hours': MAX_QUOTE_HOURS, 'baseline_asof': snapshot['asof'], 'method': 'Quote-age weighted mean of matching compounded period rates, one vote per upstream', 'limitations': 'Weights are engineering heuristics, not calibrated confidence. Futures/OIS basis unadjusted. Changes remain versus curve-date overnight anchor. Mixed quote times.'}
        L165: if not matched: goto 1396
        L166: snapshot['display_source'] = 'ICE/Eurex | mixed quote times'
        L167: snapshot['method'] = snapshot['composite']['method']
        L168: @1396: ; return snapshot

        def apply_composite.<locals>.<listcomp>(.0):   # line 136
            L136: for-next .0 (exhausted->72) ; r = <item> ; append iter(r.items())() ; goto 6 ; @72: ; return func<code <dictcomp>>

            def apply_composite.<locals>.<listcomp>.<dictcomp>(.0):   # line 136
                L136: for-next .0 (exhausted->36) ; k = <item>[0] ; v = <item>[1] ; if not (k != 'payload'): goto 6 ; map-add k: v ; goto 6 ; @36: ; return .0

        def apply_composite.<locals>.<listcomp>(.0):   # line 151
            L151: for-next .0 (exhausted->86) ; r = <item> ; if not ((r['start'], r['end']) == (meeting['start'], meeting['end'])): goto 8 ; append r ; goto 8 ; @86: ; return .0

    def reference_check(http, now):   # line 171
        """Connect the new free curve API, but do not misapply long par rates."""
        L173: [now or ...] (else goto 54) ; @54: ; now = datetime.now(UTC)
        L175: record = cached_get(http, 'checkmyswap', 'https://www.checkmyswap.com/api/curves/all', now, 86400)
        L176: summaries = {}
        L177: for-next iter(record['payload'].items()) (exhausted->364) ; currency = <item>[0] ; item = <item>[1]
        L178: rows = item.get('curve', [])
        L179: summaries[currency] = {'asof': func<code <genexpr>>(iter(rows)(), default=None), 'shortest_days': sorted, 'upstreams': func<code <setcomp>>(iter(rows)()), 'included_in_meeting_composite': False, 'reason': 'Par-tenor curve is not a dated meeting observation; Eurex-derived rows duplicate our primary source'} ; goto 152
        L184: @364:
        L184: result = {'url': record['url'], 'fetched_at': record['fetched_at'], 'currencies': summaries, 'refresh_error': record.get('refresh_error')} ; goto 524 ; except-handler:
        L186: except Exception? ; if not match(Exception): goto 516 ; exc = <exc>
        L187: result = {'error': str(exc), 'included_in_meeting_composite': False} ; pop_except ; exc = None ; del exc ; goto 524 ; exc = None ; del exc ; reraise
        L186: @516: ; reraise ; pop_except ; reraise
        L188: @524: ; @576: ; write_text((data_dir() / 'market_reference_status.json'), json.dumps(result, indent=2)) ; return None

        def reference_check.<locals>.<genexpr>(.0):   # line 180
            L180: ? ; for-next .0 (exhausted->34) ; r = <item> ; (yield r['days']) ; goto 8 ; @34: ; return None

        def reference_check.<locals>.<setcomp>(.0):   # line 181
            L181: for-next .0 (exhausted->56) ; r = <item> ; set-add r.get('source', 'unknown') ; goto 6 ; @56: ; return .0