import requests
import time
import argparse
import re
import sys

# Zabbix server details
ZABBIX_URL = "http://<your_zabbix_server>/api_jsonrpc.php"  # Replace with your Zabbix server URL
API_TOKEN = "your_api_token"  # Replace with your Zabbix API token

# Headers for API requests
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_TOKEN}"
}

# Function to parse the time argument (e.g., "1h" or "30m")
def parse_time_arg(time_str):
    match = re.match(r'(\d+)([hm])', time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}. Use '1h', '30m', etc.")

    value, unit = match.groups()
    value = int(value)

    if unit == 'h':
        return value * 3600  # Convert hours to seconds
    elif unit == 'm':
        return value * 60  # Convert minutes to seconds
    else:
        raise ValueError(f"Unsupported time unit: {unit}")

# Function to get the host ID based on the host name
def get_host_id(host_name):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid"],
            "filter": {
                "host": [host_name]
            }
        },
        "id": 1
    }

    response = requests.post(ZABBIX_URL, headers=HEADERS, json=payload)
    result = response.json()

    if "error" in result:
        raise Exception(f"Error fetching host ID for {host_name}: {result['error']['data']}")

    if result['result']:
        return result['result'][0]['hostid']
    else:
        raise Exception(f"Host {host_name} not found")

# Function to create maintenance and return the maintenance ID
def create_maintenance(host_id, host_name, duration):
    start_time = int(time.time())
    end_time = start_time + duration

    payload = {
        "jsonrpc": "2.0",
        "method": "maintenance.create",
        "params": {
            "name": f"Maintenance for host {host_name}",
            "active_since": start_time,
            "active_till": end_time,
            "hostids": [host_id],
            "timeperiods": [{
                "timeperiod_type": 0,
                "period": duration
            }]
        },
        "id": 1
    }

    response = requests.post(ZABBIX_URL, headers=HEADERS, json=payload)
    result = response.json()

    if "error" in result:
        raise Exception(f"Error creating maintenance for {host_name}: {result['error']['data']}")

    # Returning maintenance ID
    return result['result']['maintenanceids'][0]

# Main function
def main():
    parser = argparse.ArgumentParser(description="Create Zabbix maintenance for one or more hosts")
    parser.add_argument("--host", required=True, help="Comma-separated hostnames for which to create maintenance")
    parser.add_argument("-t", "--time", required=True, help="Maintenance duration (e.g., '1h', '30m')")

    args = parser.parse_args()

    # Split the comma-separated hostnames
    host_names = args.host.split(',')
    duration_str = args.time

    try:
        # Step 1: Parse the duration argument
        duration_seconds = parse_time_arg(duration_str)

        # Step 2: Process each host individually
        for host_name in host_names:
            host_name = host_name.strip()  # Remove any leading/trailing whitespace
            if not host_name:
                continue  # Skip empty hostnames

            try:
                # Step 3: Get the host ID
                host_id = get_host_id(host_name)

                # Step 4: Create maintenance for the host with the specified duration
                maintenance_id = create_maintenance(host_id, host_name, duration_seconds)

                # Step 5: Print the host ID and maintenance ID
                print(f"Successfully created maintenance for host {host_name} with:")
                print(f"- Host ID: {host_id}")
                print(f"- Maintenance ID: {maintenance_id}")
                print(f"Duration: {duration_str}")
            except Exception as e:
                print(f"Error processing host {host_name}: {e}")

    except Exception as e:
        print(str(e))

if __name__ == "__main__":
    main()
