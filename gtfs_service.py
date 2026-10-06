import os
import re
import io
import csv
import time
import math
import html
import zipfile
import urllib.request
from datetime import datetime, timedelta
from google.transit import gtfs_realtime_pb2

from config import (
    EUROSTAR_TZ,
    EUROPEAN_SLEEPER_TZ,
    EUROSTAR_RT_URL,
    EUROSTAR_STATIC_URL,
    STATIC_CACHE_FILE,
    EUROPEAN_SLEEPER_STATIC_URL,
    EUROPEAN_SLEEPER_CACHE_FILE,
    STATION_NAMES
)
from rail_routing_service import rail_router

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    return ' '.join(html.unescape(text).split())

def get_preferred_text(translated_string):
    if not translated_string or not translated_string.translation:
        return ""
    translations = {t.language: t.text for t in translated_string.translation}
    if 'fr' in translations and translations['fr'].strip():
        return translations['fr'].replace('\ufffd', 'e')
    if 'en' in translations and translations['en'].strip():
        return translations['en']
    return translated_string.translation[0].text

def format_station_label(stop_id):
    if not stop_id:
        return "Gare non renseignée"
    m = re.match(r'^(.*?)(?:_(\d+[a-zA-Z]?))?$', stop_id)
    if m:
        base, track = m.group(1), m.group(2)
        name = STATION_NAMES.get(base, base.replace('_', ' ').title())
        return f"{name} (Voie {track})" if track else name
    return STATION_NAMES.get(stop_id, stop_id.replace('_', ' ').title())

def format_delay(delay_seconds):
    if delay_seconds <= 0:
        return "À l'heure"
    mins = delay_seconds // 60
    secs = delay_seconds % 60
    return f"+{mins} min" if mins > 0 else f"+{secs}s"

def calculate_bearing(lat1, lon1, lat2, lon2):
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - \
        math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360

def haversine_dist(p1, p2):
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def interpolate_along_track(pts, ratio):
    """Calcule la position et l'orientation exacte le long d'une polyline ferroviaire."""
    if not pts:
        return [0.0, 0.0], 0.0
    if len(pts) == 1:
        return pts[0], 0.0
    ratio = min(1.0, max(0.0, ratio))
    dists = [haversine_dist(pts[i], pts[i+1]) for i in range(len(pts)-1)]
    total_dist = sum(dists)
    if total_dist == 0:
        return pts[0], 0.0

    target = ratio * total_dist
    accum = 0.0
    for i, d in enumerate(dists):
        if accum + d >= target:
            seg_r = (target - accum) / d if d > 0 else 0
            lat = pts[i][0] + (pts[i+1][0] - pts[i][0]) * seg_r
            lon = pts[i][1] + (pts[i+1][1] - pts[i][1]) * seg_r
            b = calculate_bearing(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
            return [round(lat, 6), round(lon, 6)], round(b, 1)
        accum += d

    p_last = pts[-1]
    p_prev = pts[-2]
    return p_last, round(calculate_bearing(p_prev[0], p_prev[1], p_last[0], p_last[1]), 1)

def extract_sub_shape(full_shape, cur_lat, cur_lon, nxt_lat, nxt_lon):
    """Extrait le tronçon ferroviaire entre deux gares consécutives le long de la shape complète."""
    if not full_shape or len(full_shape) < 2:
        return None
    i_start = min(range(len(full_shape)), key=lambda i: haversine_dist(full_shape[i], (cur_lat, cur_lon)))
    i_end = min(range(len(full_shape)), key=lambda i: haversine_dist(full_shape[i], (nxt_lat, nxt_lon)))
    if i_start == i_end:
        return None
    if i_start < i_end:
        return full_shape[i_start : i_end + 1]
    else:
        return list(reversed(full_shape[i_end : i_start + 1]))

def parse_time_sec(hms):
    parts = [int(p) for p in hms.split(':')]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]

def get_static_gtfs():
    """Télécharge ou utilise le cache du GTFS statique Eurostar."""
    need_download = True
    if os.path.exists(STATIC_CACHE_FILE):
        file_age = time.time() - os.path.getmtime(STATIC_CACHE_FILE)
        if file_age < 86400:
            need_download = False

    if need_download:
        print("📦 Téléchargement du GTFS statique Eurostar (horaires & réseau)...")
        try:
            req = urllib.request.Request(EUROSTAR_STATIC_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(STATIC_CACHE_FILE, 'wb') as f:
                    f.write(resp.read())
        except Exception as e:
            print(f"⚠️ Échec du téléchargement Eurostar GTFS ({e}), tentative avec cache existant...")

    with open(STATIC_CACHE_FILE, 'rb') as f:
        return zipfile.ZipFile(io.BytesIO(f.read()))

def get_european_sleeper_gtfs():
    """Télécharge ou utilise le cache du GTFS European Sleeper."""
    need_download = True
    if os.path.exists(EUROPEAN_SLEEPER_CACHE_FILE):
        file_age = time.time() - os.path.getmtime(EUROPEAN_SLEEPER_CACHE_FILE)
        if file_age < 86400:
            need_download = False

    if need_download:
        print("📦 Téléchargement du GTFS European Sleeper (trains de nuit)...")
        try:
            req = urllib.request.Request(EUROPEAN_SLEEPER_STATIC_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(EUROPEAN_SLEEPER_CACHE_FILE, 'wb') as f:
                    f.write(resp.read())
        except Exception as e:
            print(f"⚠️ Échec du téléchargement European Sleeper ({e}), tentative avec cache local...")

    with open(EUROPEAN_SLEEPER_CACHE_FILE, 'rb') as f:
        return zipfile.ZipFile(io.BytesIO(f.read()))

def build_eurostar_data():
    """Analyse le réseau Eurostar (GTFS statique + GTFS-RT)."""
    zf = get_static_gtfs()

    # 1. Stops & gares
    stops = {}
    stations_map = {}
    with zf.open('stops.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
        for r in reader:
            sid = r['stop_id']
            lat = float(r['stop_lat'])
            lon = float(r['stop_lon'])
            stops[sid] = {
                'name': r['stop_name'],
                'lat': lat,
                'lon': lon,
                'platform': r.get('platform_code', '')
            }
            base_id = re.sub(r'_\d+[a-zA-Z]?$', '', sid).replace('_station_area', '')
            if base_id not in stations_map:
                stations_map[base_id] = {
                    'id': f"eurostar_{base_id}",
                    'name': STATION_NAMES.get(base_id, r['stop_name'].replace('-', ' ')),
                    'lat': lat,
                    'lon': lon,
                    'network': 'eurostar'
                }

    # 2. Shapes
    shapes_raw = {}
    with zf.open('shapes.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
        for r in reader:
            sid = r['shape_id']
            if sid not in shapes_raw:
                shapes_raw[sid] = []
            shapes_raw[sid].append([float(r['shape_pt_lat']), float(r['shape_pt_lon'])])

    shapes_dict = {}
    for sid, pts in shapes_raw.items():
        sampled = pts[::3]
        if sampled[-1] != pts[-1]:
            sampled.append(pts[-1])
        shapes_dict[sid] = sampled

    # Corridors transmanche
    hs1_pts = [] # Londres -> Lille Europe (HS1 + Tunnel)
    lille_paris = rail_router.get_rail_segment(50.6389, 3.0758, 48.8809, 2.3553) # Lille Europe -> Paris Nord (LGV Nord)
    lille_bruxelles = rail_router.get_rail_segment(50.6389, 3.0758, 50.8353, 4.3358) # Lille Europe -> Bruxelles-Midi (HSL 1)

    raw_5814 = shapes_raw.get('5814', [])
    raw_628 = shapes_raw.get('628', [])

    london_paris = hs1_pts + lille_paris[1:]
    paris_london = list(reversed(london_paris))

    london_bruxelles = hs1_pts + lille_bruxelles[1:]
    bruxelles_london = list(reversed(london_bruxelles))

    shapes_dict['CORRIDOR_GBSPX_FRPNO'] = london_paris
    shapes_dict['CORRIDOR_FRPNO_GBSPX'] = paris_london
    shapes_dict['CORRIDOR_GBSPX_BEBMI'] = london_bruxelles
    shapes_dict['CORRIDOR_BEBMI_GBSPX'] = bruxelles_london
    if raw_5814:
        shapes_dict['CORRIDOR_GBSPX_NLAMA'] = london_bruxelles + raw_5814[::2]
    if raw_628:
        shapes_dict['CORRIDOR_NLAMA_GBSPX'] = raw_628[::2] + bruxelles_london
        shapes_dict['CORRIDOR_NLRTA_GBSPX'] = raw_628[::2] + bruxelles_london

    raw_6023 = shapes_raw.get('6023', [])
    if raw_6023:
        be_mlv = shapes_raw['6023'][::3]
        shapes_dict['CORRIDOR_BEBMI_FRMLV'] = be_mlv
        shapes_dict['CORRIDOR_FRMLV_BEBMI'] = list(reversed(be_mlv))
        if raw_628:
            shapes_dict['CORRIDOR_NLAMA_FRMLV'] = shapes_raw['628'][::3] + be_mlv
        if raw_5814:
            shapes_dict['CORRIDOR_FRMLV_NLAMA'] = list(reversed(be_mlv)) + shapes_raw['5814'][::3]

    # 3. Trips aujourd'hui
    now = datetime.now(EUROSTAR_TZ)
    today_suffix = now.strftime('%m%d')
    today_trips = {}
    with zf.open('trips.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
        for r in reader:
            tid = r['trip_id']
            if tid.endswith('-' + today_suffix):
                today_trips[tid] = {
                    'headsign': r['trip_headsign'],
                    'train_num': r['trip_short_name'],
                    'route_id': r.get('route_id', ''),
                    'shape_id': r.get('shape_id', '')
                }

    # 4. Stop times
    trip_stops = {}
    with zf.open('stop_times.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
        for r in reader:
            tid = r['trip_id']
            if tid in today_trips:
                if tid not in trip_stops:
                    trip_stops[tid] = []
                trip_stops[tid].append({
                    'stop_id': r['stop_id'],
                    'seq': int(r['stop_sequence']),
                    'arr': r['arrival_time'],
                    'dep': r['departure_time']
                })

    for tid in trip_stops:
        trip_stops[tid].sort(key=lambda x: x['seq'])

    # 5. GTFS-RT (retards & alertes)
    rt_delays = {}
    rt_alerts = {}
    try:
        req = urllib.request.Request(EUROSTAR_RT_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(resp.read())

        for e in feed.entity:
            if e.HasField('alert'):
                header = clean_html(get_preferred_text(e.alert.header_text))
                desc = clean_html(get_preferred_text(e.alert.description_text))
                alert_text = desc if desc else header
                for ie in e.alert.informed_entity:
                    if ie.HasField('trip') and ie.trip.trip_id:
                        rt_alerts[ie.trip.trip_id] = alert_text
                        num = ie.trip.trip_id.split('-')[0]
                        rt_alerts[num] = alert_text

            if e.HasField('trip_update'):
                tu = e.trip_update
                tid = tu.trip.trip_id
                is_trip_canceled = False
                if tu.trip.HasField('schedule_relationship'):
                    if tu.trip.schedule_relationship == gtfs_realtime_pb2.TripDescriptor.ScheduleRelationship.CANCELED:
                        is_trip_canceled = True

                seq_info = {}
                for s in tu.stop_time_update:
                    assigned = s.stop_time_properties.assigned_stop_id if s.HasField('stop_time_properties') else ""
                    is_skipped = False
                    if s.HasField('schedule_relationship'):
                        if s.schedule_relationship == gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.ScheduleRelationship.SKIPPED:
                            is_skipped = True

                    seq_info[s.stop_sequence] = {
                        'arr_delay': s.arrival.delay if s.HasField('arrival') else 0,
                        'dep_delay': s.departure.delay if s.HasField('departure') else 0,
                        'assigned': assigned,
                        'is_skipped': is_skipped
                    }
                rt_delays[tid] = {
                    'stops': seq_info,
                    'is_canceled': is_trip_canceled
                }
    except Exception as ex:
        print(f"⚠️ Erreur lors de la lecture GTFS-RT Eurostar ({ex})")

    # 6. Positions et statuts
    now_sec = now.hour * 3600 + now.minute * 60 + now.second
    trains_list = []

    for tid, t_meta in today_trips.items():
        s_list = trip_stops.get(tid, [])
        if not s_list:
            continue

        rt_trip_data = rt_delays.get(tid, {})
        delays_map = rt_trip_data.get('stops', {}) if isinstance(rt_trip_data, dict) and 'stops' in rt_trip_data else {}
        is_trip_canceled = rt_trip_data.get('is_canceled', False) if isinstance(rt_trip_data, dict) else False
        alert_msg = rt_alerts.get(tid) or rt_alerts.get(t_meta['train_num'])

        enriched_stops = []
        max_train_delay = 0

        for s in s_list:
            seq = s['seq']
            rt_info = delays_map.get(seq, {})
            arr_delay = rt_info.get('arr_delay', 0)
            dep_delay = rt_info.get('dep_delay', 0)
            assigned_track = rt_info.get('assigned', '')
            is_skipped = rt_info.get('is_skipped', False)

            max_train_delay = max(max_train_delay, arr_delay, dep_delay)

            sched_arr_sec = parse_time_sec(s['arr'])
            sched_dep_sec = parse_time_sec(s['dep'])
            est_arr_sec = sched_arr_sec + arr_delay
            est_dep_sec = sched_dep_sec + dep_delay

            stop_coord = stops.get(s['stop_id'], {'lat': 0.0, 'lon': 0.0, 'name': s['stop_id']})
            stop_display_name = format_station_label(assigned_track if assigned_track else s['stop_id'])

            enriched_stops.append({
                'seq': seq,
                'stop_id': s['stop_id'],
                'name': stop_display_name,
                'lat': stop_coord['lat'],
                'lon': stop_coord['lon'],
                'sched_arr': s['arr'][:5],
                'sched_dep': s['dep'][:5],
                'est_arr': f"{(est_arr_sec//3600)%24:02d}:{(est_arr_sec%3600)//60:02d}",
                'est_dep': f"{(est_dep_sec//3600)%24:02d}:{(est_dep_sec%3600)//60:02d}",
                'sched_arr_sec': sched_arr_sec,
                'sched_dep_sec': sched_dep_sec,
                'est_arr_sec': est_arr_sec,
                'est_dep_sec': est_dep_sec,
                'delay_arr': arr_delay,
                'delay_dep': dep_delay,
                'track': assigned_track,
                'is_skipped': is_skipped
            })

        active_stops = [s for s in enriched_stops if not s['is_skipped']]
        has_skipped = any(s['is_skipped'] for s in enriched_stops)
        skipped_count = sum(1 for s in enriched_stops if s['is_skipped'])

        assigned_shape_id = t_meta.get('shape_id', '')
        if not assigned_shape_id or assigned_shape_id not in shapes_dict:
            route_corridor_id = f"CORRIDOR_{t_meta.get('route_id', '').replace('-', '_')}"
            if route_corridor_id in shapes_dict:
                assigned_shape_id = route_corridor_id

        time_to_dep_sec = None
        is_departing_soon = False

        if not active_stops or is_trip_canceled:
            is_trip_canceled = True
            status = "CANCELED"
            status_label = "Train annulé / supprimé"
            first_stop = enriched_stops[0]
            last_stop = enriched_stops[-1]
            origin_name = first_stop['name'].split('(')[0].strip()
            dest_name = last_stop['name'].split('(')[0].strip()
            pos = [first_stop['lat'], first_stop['lon']]
            bearing = 0
            progress = 0.0
            time_to_dep_sec = first_stop['est_dep_sec'] - now_sec
            is_departing_soon = (0 <= time_to_dep_sec <= 1200)
        else:
            first_stop = active_stops[0]
            last_stop = active_stops[-1]
            origin_name = first_stop['name'].split('(')[0].strip()
            dest_name = last_stop['name'].split('(')[0].strip()

            if enriched_stops[-1]['is_skipped']:
                dest_name = f"{dest_name} (Terminus adapté)"

            status = "SCHEDULED"
            status_label = f"Départ prévu à {first_stop['est_dep']}"
            pos = [first_stop['lat'], first_stop['lon']]
            bearing = 0
            progress = 0.0

            time_to_dep_sec = first_stop['est_dep_sec'] - now_sec
            is_departing_soon = (0 <= time_to_dep_sec <= 1200)

            if now_sec < first_stop['est_dep_sec']:
                status = "SCHEDULED"
                if is_departing_soon:
                    mins = max(1, time_to_dep_sec // 60)
                    status_label = f"À quai à {origin_name} (départ dans {mins} min à {first_stop['est_dep']})"
                else:
                    status_label = f"À quai à {origin_name} (départ prévu à {first_stop['est_dep']})"
                pos = [first_stop['lat'], first_stop['lon']]
            elif now_sec >= last_stop['est_arr_sec']:
                status = "TERMINATED"
                status_label = f"Arrivé au terminus ({dest_name})"
                pos = [last_stop['lat'], last_stop['lon']]
                progress = 1.0
            else:
                status = "RUNNING"
                for i in range(len(active_stops) - 1):
                    cur_s = active_stops[i]
                    nxt_s = active_stops[i + 1]

                    if cur_s['est_arr_sec'] <= now_sec <= cur_s['est_dep_sec']:
                        status_label = f"À quai à {cur_s['name']} (départ {cur_s['est_dep']})"
                        pos = [cur_s['lat'], cur_s['lon']]
                        progress = float(i) / (len(active_stops) - 1)
                        break
                    elif cur_s['est_dep_sec'] < now_sec < nxt_s['est_arr_sec']:
                        seg_duration = max(1, nxt_s['est_arr_sec'] - cur_s['est_dep_sec'])
                        seg_elapsed = now_sec - cur_s['est_dep_sec']
                        seg_ratio = min(1.0, max(0.0, seg_elapsed / seg_duration))

                        # 1. Recherche du tracé exact sur la voie ferrée réelle
                        full_shape = shapes_dict.get(assigned_shape_id)
                        track_sub = extract_sub_shape(full_shape, cur_s['lat'], cur_s['lon'], nxt_s['lat'], nxt_s['lon'])
                        if not track_sub or len(track_sub) < 2:
                            track_sub = rail_router.get_rail_segment(cur_s['lat'], cur_s['lon'], nxt_s['lat'], nxt_s['lon'])

                        if track_sub and len(track_sub) >= 2:
                            pos, bearing = interpolate_along_track(track_sub, seg_ratio)
                        else:
                            interp_lat = cur_s['lat'] + (nxt_s['lat'] - cur_s['lat']) * seg_ratio
                            interp_lon = cur_s['lon'] + (nxt_s['lon'] - cur_s['lon']) * seg_ratio
                            pos = [round(interp_lat, 6), round(interp_lon, 6)]
                            bearing = calculate_bearing(cur_s['lat'], cur_s['lon'], nxt_s['lat'], nxt_s['lon'])

                        next_station_clean = nxt_s['name'].split('(')[0].strip()
                        pct = int(seg_ratio * 100)
                        status_label = f"En circulation vers {next_station_clean} ({pct}%)"
                        progress = (i + seg_ratio) / (len(active_stops) - 1)
                        break

        trains_list.append({
            'id': tid,
            'num': t_meta['train_num'],
            'headsign': t_meta['headsign'],
            'origin': origin_name,
            'destination': dest_name,
            'status': status,
            'status_label': status_label,
            'lat': pos[0],
            'lon': pos[1],
            'bearing': round(bearing, 1),
            'progress': round(progress, 2),
            'delay_sec': max_train_delay,
            'delay_str': format_delay(max_train_delay),
            'is_canceled': is_trip_canceled,
            'has_skipped': has_skipped,
            'skipped_count': skipped_count,
            'alert': alert_msg,
            'stops': enriched_stops,
            'shape_id': assigned_shape_id,
            'network': 'eurostar',
            'operator_name': 'Eurostar',
            'time_to_dep_sec': time_to_dep_sec,
            'is_departing_soon': is_departing_soon
        })

    return {
        'trains': trains_list,
        'shapes_dict': shapes_dict,
        'stations': list(stations_map.values())
    }

def build_european_sleeper_data():
    """Analyse le réseau European Sleeper (trains de nuit trans-européens)."""
    zf = get_european_sleeper_gtfs()

    # 1. Stops & gares
    stops = {}
    stations_map = {}
    with zf.open('stops.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
        for r in reader:
            sid = r['stop_id']
            lat = float(r['stop_lat'])
            lon = float(r['stop_lon'])
            stops[sid] = {
                'id': sid,
                'name': r['stop_name'],
                'lat': lat,
                'lon': lon
            }
            stations_map[sid] = {
                'id': f"es_{sid}",
                'name': r['stop_name'],
                'lat': lat,
                'lon': lon,
                'network': 'european_sleeper'
            }

    # 2. Calendar dates
    calendar_dates = {}
    with zf.open('calendar_dates.txt') as f:
        for r in csv.DictReader(io.TextIOWrapper(f, encoding='utf-8')):
            if r['exception_type'] == '1':
                d = r['date']
                calendar_dates.setdefault(d, set()).add(r['service_id'])

    # 3. Trips & Stop times
    trips = {}
    with zf.open('trips.txt') as f:
        for r in csv.DictReader(io.TextIOWrapper(f, encoding='utf-8')):
            trips[r['trip_id']] = r

    trip_stops = {}
    with zf.open('stop_times.txt') as f:
        for r in csv.DictReader(io.TextIOWrapper(f, encoding='utf-8')):
            tid = r['trip_id']
            trip_stops.setdefault(tid, []).append({
                'stop_id': r['stop_id'],
                'seq': int(r['stop_sequence']),
                'arr': r['arrival_time'],
                'dep': r['departure_time'],
                'arr_sec': parse_time_sec(r['arrival_time']),
                'dep_sec': parse_time_sec(r['departure_time'])
            })

    for tid in trip_stops:
        trip_stops[tid].sort(key=lambda x: x['seq'])

    # Date de référence
    now = datetime.now(EUROPEAN_SLEEPER_TZ)
    now_sec = now.hour * 3600 + now.minute * 60 + now.second
    today_str = now.strftime('%Y%m%d')
    yesterday_str = (now - timedelta(days=1)).strftime('%Y%m%d')

    # Gestion des jours de service actifs (départ hier soir et départ ce soir)
    active_service_days = []
    if yesterday_str in calendar_dates:
        for s in calendar_dates[yesterday_str]:
            active_service_days.append((s, -1))
    if today_str in calendar_dates:
        for s in calendar_dates[today_str]:
            active_service_days.append((s, 0))

    # Si la date actuelle n'est pas dans le calendrier (hors saison/archive), repli gracieux sur les dates les plus récentes
    if not active_service_days and calendar_dates:
        all_sorted = sorted(calendar_dates.keys())
        sim_date = all_sorted[0]
        for s in calendar_dates[sim_date]:
            active_service_days.append((s, 0))

    shapes_dict = {}
    trains_list = []

    for sid, day_offset in active_service_days:
        t_meta = trips.get(sid)
        if not t_meta:
            continue
        s_list = trip_stops.get(sid, [])
        if not s_list:
            continue

        # Référence temporelle : si départ hier, l'heure actuelle équivaut à (now_sec + 86400)
        t_ref = now_sec - (day_offset * 86400)

        first_stop = s_list[0]
        last_stop = s_list[-1]
        origin_name = stops[first_stop['stop_id']]['name']
        dest_name = stops[last_stop['stop_id']]['name']

        enriched_stops = []
        shape_pts = []

        for s in s_list:
            st = stops.get(s['stop_id'], {'name': s['stop_id'], 'lat': 0.0, 'lon': 0.0})
            shape_pts.append([st['lat'], st['lon']])

            ah = (s['arr_sec'] // 3600) % 24
            am = (s['arr_sec'] % 3600) // 60
            dh = (s['dep_sec'] // 3600) % 24
            dm = (s['dep_sec'] % 3600) // 60

            next_day_arr = ' (+1j)' if s['arr_sec'] >= 86400 else ''
            next_day_dep = ' (+1j)' if s['dep_sec'] >= 86400 else ''

            enriched_stops.append({
                'seq': s['seq'],
                'stop_id': s['stop_id'],
                'name': st['name'],
                'lat': st['lat'],
                'lon': st['lon'],
                'sched_arr': f"{ah:02d}:{am:02d}{next_day_arr}",
                'sched_dep': f"{dh:02d}:{dm:02d}{next_day_dep}",
                'est_arr': f"{ah:02d}:{am:02d}{next_day_arr}",
                'est_dep': f"{dh:02d}:{dm:02d}{next_day_dep}",
                'sched_arr_sec': s['arr_sec'],
                'sched_dep_sec': s['dep_sec'],
                'est_arr_sec': s['arr_sec'],
                'est_dep_sec': s['dep_sec'],
                'delay_arr': 0,
                'delay_dep': 0,
                'track': '',
                'is_skipped': False
            })

        # Génération du tracé ferroviaire réel via OpenStreetMap
        stops_coords = [[s['lat'], s['lon']] for s in enriched_stops]
        full_rail_pts = rail_router.get_full_route(stops_coords)
        shape_id = f"SHAPE_ES_{sid}"
        shapes_dict[shape_id] = full_rail_pts

        time_to_dep_sec = first_stop['dep_sec'] - t_ref
        is_departing_soon = (t_ref < first_stop['dep_sec'] and 0 <= time_to_dep_sec <= 1200)

        if t_ref < first_stop['dep_sec']:
            status = 'SCHEDULED'
            dep_disp = enriched_stops[0]['sched_dep']
            if is_departing_soon:
                mins = max(1, time_to_dep_sec // 60)
                status_label = f"À quai à {origin_name} (départ dans {mins} min à {dep_disp})"
            else:
                status_label = f"À quai à {origin_name} (départ {dep_disp})"
            pos = [enriched_stops[0]['lat'], enriched_stops[0]['lon']]
            bearing = 0
            progress = 0.0
        elif t_ref >= last_stop['arr_sec']:
            status = 'TERMINATED'
            status_label = f"Arrivé au terminus ({dest_name})"
            pos = [enriched_stops[-1]['lat'], enriched_stops[-1]['lon']]
            bearing = 0
            progress = 1.0
        else:
            status = 'RUNNING'
            bearing = 0
            pos = [enriched_stops[0]['lat'], enriched_stops[0]['lon']]
            progress = 0.0
            for i in range(len(s_list) - 1):
                cur_s = s_list[i]
                nxt_s = s_list[i + 1]
                if cur_s['arr_sec'] <= t_ref <= cur_s['dep_sec']:
                    dep_disp = enriched_stops[i]['sched_dep']
                    cur_name = stops[cur_s['stop_id']]['name']
                    status_label = f"À quai à {cur_name} (départ {dep_disp})"
                    pos = [stops[cur_s['stop_id']]['lat'], stops[cur_s['stop_id']]['lon']]
                    progress = float(i) / (len(s_list) - 1)
                    break
                elif cur_s['dep_sec'] < t_ref < nxt_s['arr_sec']:
                    dur = max(1, nxt_s['arr_sec'] - cur_s['dep_sec'])
                    ratio = min(1.0, max(0.0, (t_ref - cur_s['dep_sec']) / dur))
                    c_st = stops[cur_s['stop_id']]
                    n_st = stops[nxt_s['stop_id']]

                    # Positionnement exact sur la voie ferrée réelle
                    seg = rail_router.get_rail_segment(c_st['lat'], c_st['lon'], n_st['lat'], n_st['lon'])
                    if len(seg) >= 2:
                        idx = min(len(seg) - 1, max(0, int(ratio * (len(seg) - 1))))
                        pos = seg[idx]
                        nxt_idx = min(len(seg) - 1, idx + 1)
                        if nxt_idx != idx:
                            bearing = calculate_bearing(pos[0], pos[1], seg[nxt_idx][0], seg[nxt_idx][1])
                        else:
                            bearing = calculate_bearing(c_st['lat'], c_st['lon'], n_st['lat'], n_st['lon'])
                    else:
                        pos = [
                            round(c_st['lat'] + (n_st['lat'] - c_st['lat']) * ratio, 6),
                            round(c_st['lon'] + (n_st['lon'] - c_st['lon']) * ratio, 6)
                        ]
                        bearing = calculate_bearing(c_st['lat'], c_st['lon'], n_st['lat'], n_st['lon'])

                    progress = (i + ratio) / (len(s_list) - 1)
                    pct = int(ratio * 100)
                    status_label = f"En circulation vers {n_st['name']} ({pct}%)"
                    break

        train_id = f"{sid}_{'D0' if day_offset == 0 else 'Dm1'}"
        trains_list.append({
            'id': train_id,
            'num': t_meta['trip_short_name'],
            'headsign': t_meta['trip_headsign'],
            'origin': origin_name,
            'destination': dest_name,
            'status': status,
            'status_label': status_label,
            'lat': pos[0],
            'lon': pos[1],
            'bearing': round(bearing, 1),
            'progress': round(progress, 2),
            'delay_sec': 0,
            'delay_str': "À l'heure (théorique)",
            'is_canceled': False,
            'has_skipped': False,
            'skipped_count': 0,
            'alert': '',
            'stops': enriched_stops,
            'network': 'european_sleeper',
            'operator_name': 'European Sleeper',
            'shape_id': shape_id,
            'time_to_dep_sec': time_to_dep_sec,
            'is_departing_soon': is_departing_soon
        })

    return {
        'trains': trains_list,
        'shapes_dict': shapes_dict,
        'stations': list(stations_map.values())
    }

def build_network_data():
    """Charge et unifie les données des réseaux Eurostar et European Sleeper."""
    now = datetime.now(EUROSTAR_TZ)

    # 1. Chargement Eurostar
    try:
        eurostar = build_eurostar_data()
    except Exception as e:
        print(f"⚠️ Erreur lors du chargement Eurostar ({e})")
        eurostar = {'trains': [], 'shapes_dict': {}, 'stations': []}

    # 2. Chargement European Sleeper
    try:
        sleeper = build_european_sleeper_data()
    except Exception as e:
        print(f"⚠️ Erreur lors du chargement European Sleeper ({e})")
        sleeper = {'trains': [], 'shapes_dict': {}, 'stations': []}

    # 3. Fusion des trains et filtrage strict :
    # Conserver EXCLUSIVEMENT les trains en cours de circulation et ceux qui partent dans moins de 20 min (<= 1200 s)
    all_trains = eurostar['trains'] + sleeper['trains']
    radar_trains = []
    for t in all_trains:
        if t['status'] == 'RUNNING':
            radar_trains.append(t)
        elif t['status'] == 'SCHEDULED' and (t.get('is_departing_soon') or (t.get('time_to_dep_sec') is not None and 0 <= t.get('time_to_dep_sec') <= 1200)):
            radar_trains.append(t)

    radar_trains.sort(key=lambda x: (
        0 if x['status'] == 'RUNNING' else 1,
        x.get('time_to_dep_sec', 0) if x['status'] == 'SCHEDULED' else 0,
        -x['delay_sec'],
        x['num']
    ))

    # 4. Fusion des shapes
    unified_shapes_dict = {}
    unified_shapes_dict.update(eurostar.get('shapes_dict', {}))
    unified_shapes_dict.update(sleeper.get('shapes_dict', {}))
    unified_shapes_list = list(unified_shapes_dict.values())

    # 5. Fusion et déduplication des gares
    all_stations = []
    station_seen = {}

    for st in eurostar.get('stations', []):
        key = (round(st['lat'], 3), round(st['lon'], 3))
        station_seen[key] = {
            'id': st['id'],
            'name': st['name'],
            'lat': st['lat'],
            'lon': st['lon'],
            'network': 'eurostar'
        }

    for st in sleeper.get('stations', []):
        key = (round(st['lat'], 3), round(st['lon'], 3))
        if key in station_seen:
            station_seen[key]['network'] = 'both'
        else:
            station_seen[key] = {
                'id': st['id'],
                'name': st['name'],
                'lat': st['lat'],
                'lon': st['lon'],
                'network': 'european_sleeper'
            }

    all_stations = list(station_seen.values())

    return {
        'timestamp': now.strftime('%H:%M:%S'),
        'date': now.strftime('%d/%m/%Y'),
        'networks': [
            {'id': 'all', 'name': 'Tous les réseaux (Eurostar & European Sleeper)', 'badge': '🌐'},
            {'id': 'eurostar', 'name': 'Eurostar', 'badge': '🚆', 'color': '#00d2ff'},
            {'id': 'european_sleeper', 'name': 'European Sleeper (Nuit)', 'badge': '🌙', 'color': '#a855f7'}
        ],
        'trains': radar_trains,
        'shapes': unified_shapes_list,
        'shapes_dict': unified_shapes_dict,
        'stations': all_stations
    }
