import requests
import math
import time


# Get address info from ViaCEP
def get_address(cep):
    print(f"[INFO] Fetching address for CEP: {cep}")

    url = f"https://viacep.com.br/ws/{cep}/json/"
    r = requests.get(url, timeout=10)
    r.raise_for_status()

    data = r.json()

    if "erro" in data:
        raise Exception(f"[ERROR] Invalid CEP: {cep}")

    print(f"[OK] Address found: {data['logradouro']} - {data['localidade']}/{data['uf']}")

    return data


# Get lat/lon from OpenStreetMap (Nominatim)
def get_lat_lon(address):
    query = f"{address['logradouro']}, {address['localidade']}, {address['uf']}, Brazil"

    print(f"[INFO] Geocoding: {query}")

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": query,
        "format": "json",
        "limit": 1
    }

    headers = {
        "User-Agent": "cep-distance-script"
    }

    r = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=10
    )

    r.raise_for_status()

    data = r.json()

    if not data:
        raise Exception("[ERROR] Coordinates not found")

    lat = float(data[0]["lat"])
    lon = float(data[0]["lon"])

    print(f"[OK] Coordinates: lat={lat}, lon={lon}")

    return lat, lon


# Haversine formula
def haversine(lat1, lon1, lat2, lon2):
    print("[INFO] Calculating distance (Haversine)...")

    R = 6371  # Earth radius in km

    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2 +
        math.cos(lat1) * math.cos(lat2) *
        math.sin(dlon / 2) ** 2
    )

    c = 2 * math.asin(math.sqrt(a))

    distance = R * c

    print(f"[OK] Distance calculated: {round(distance, 2)} km")

    return distance


# Main function
def cep_distance(cep1, cep2):
    print("=" * 50)
    print("[START] CEP Distance Calculation")
    print("=" * 50)

    # Get first CEP
    addr1 = get_address(cep1)

    time.sleep(1)  # Respect API limit

    # Get second CEP
    addr2 = get_address(cep2)

    time.sleep(1)

    # Get coordinates
    print("\n[STEP] Getting coordinates for CEP 1")
    lat1, lon1 = get_lat_lon(addr1)

    time.sleep(1)

    print("\n[STEP] Getting coordinates for CEP 2")
    lat2, lon2 = get_lat_lon(addr2)

    time.sleep(1)

    # Calculate distance
    print("\n[STEP] Computing final distance")
    distance_km = haversine(lat1, lon1, lat2, lon2)

    print("=" * 50)
    print("[DONE] Calculation Finished")
    print("=" * 50)

    return round(distance_km, 2)
