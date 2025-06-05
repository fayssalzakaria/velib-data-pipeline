import pandas as pd

def transform_data(json_data):
    print("🧹 Parsing + transformation...")
    records = json_data["records"]
    rows = []
    for rec in records:
        fields = rec["fields"]
        rows.append({
            "station_id": fields.get("stationcode"),
            "name": fields.get("name"),
            "numbikesavailable": fields.get("numbikesavailable"),
            "mechanical": fields.get("mechanical", 0),
            "ebike": fields.get("ebike", 0),
            "numdocksavailable": fields.get("numdocksavailable"),
            "timestamp": fields.get("duedate")
        })
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.day_name()
    df = df.dropna(subset=["station_id", "name"])
    return df
