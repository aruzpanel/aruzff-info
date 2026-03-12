from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
import lib2
import json
import asyncio
from datetime import datetime, timedelta
import pytz
import os
from concurrent.futures import ThreadPoolExecutor
import uuid

app = Flask(__name__)
CORS(app)

max_workers = min(10000, (os.cpu_count() or 1) * 1000)
executor = ThreadPoolExecutor(max_workers=max_workers)

def convert_timestamps(data, timestamp_keys):
    if isinstance(data, dict):
        for key, value in data.items():
            if key in timestamp_keys and isinstance(value, str):
                try:
                    timestamp = int(value)
                    data[key] = datetime.fromtimestamp(timestamp, pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pass
            else:
                convert_timestamps(value, timestamp_keys)
    elif isinstance(data, list):
        for item in data:
            convert_timestamps(item, timestamp_keys)

REGION_FALLBACK_ORDER = ("sg", "ind")

async def fetch_all_data(uid, region):
    personal_show = await lib2.GetAccountInformation(uid, "7", region, "/GetPlayerPersonalShow")
    return {"account_data": personal_show}

def sync_fetch_all_data(uid, region):
    return asyncio.run(fetch_all_data(uid, region))

def is_error_result(data):
    ad = data.get("account_data") if isinstance(data, dict) else None
    return isinstance(ad, dict) and "error" in ad

# API information endpoint
@app.route("/api/playerinfo")
def get_account_info():
    region = request.args.get('region')
    uid = request.args.get('uid')
    
    if not uid:
        response = {
            "error": "Invalid request",
            "message": "Empty 'uid' parameter. Please provide a valid 'uid'."
        }
        return jsonify(response), 400, {'Content-Type': 'application/json; charset=utf-8'}

    # Region optional: try given region, else auto sg then ind on failure
    regions_to_try = [region.strip().lower()] if (region and region.strip()) else []
    regions_to_try = regions_to_try + [r for r in REGION_FALLBACK_ORDER if r not in regions_to_try]

    # Try regions in order; stop as soon as one returns a valid response (no need to try rest)
    all_data = None
    for r in regions_to_try:
        try:
            future = executor.submit(sync_fetch_all_data, uid, r)
            all_data = future.result()
            if not is_error_result(all_data):
                break  # got valid response, show it and do not try ind or others
        except Exception:
            all_data = {"account_data": {"error": "Request failed", "message": f"Region {r} failed"}}
            continue  # this region failed, try next (e.g. sg fail then try ind)

    if all_data is None or is_error_result(all_data):
        msg = (all_data or {}).get("account_data", {}).get("message", "All regions failed. Try again later.") if all_data else "All regions failed. Try again later."
        response = {"error": "Service unavailable", "message": msg}
        return jsonify(response), 503, {'Content-Type': 'application/json; charset=utf-8'}

    timestamp_keys = ["lastLoginAt", "createAt", "periodicSummaryEndTime"]
    convert_timestamps(all_data, timestamp_keys)
    
    # Return only nickname, level, createAt, liked
    ad = all_data.get("account_data")
    if isinstance(ad, dict) and "error" not in ad:
        basic = ad.get("basicInfo") or {}
        all_data = {
            "account_data": {
                "nickname": basic.get("nickname"),
                "level": basic.get("level"),
                "createAt": basic.get("createAt"),
                "liked": basic.get("liked")
            }
        }
    
    formatted_json = json.dumps(all_data, indent=2, ensure_ascii=False)
    return formatted_json, 200, {'Content-Type': 'application/json; charset=utf-8'}

# No API key management needed.

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
