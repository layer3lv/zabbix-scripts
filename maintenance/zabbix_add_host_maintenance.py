import requests
import time
import argparse
import re
import os

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

# Function to get all host IDs
def get_all_host_ids():
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "host"]
        },
        "id": 1
    }

    response = requests.post(ZABBIX_URL, headers=HEADERS, json=payload)
    result = response.json()

    if "error" in result:
        raise Exception(f"Error fetching all hosts: {result['error']['data']}")

    hosts = result['result']
    return {host['host']: host['hostid'] for host in hosts}

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
def create_maintenance(host_ids, duration):
    start_time = int(time.time())
    end_time = start_time + duration

    payload = {
        "jsonrpc": "2.0",
        "method": "maintenance.create",
        "params": {
            "name": "Maintenance for selected hosts",
            "active_since": start_time,
            "active_till": end_time,
            "hostids": host_ids,
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
        raise Exception(f"Error creating maintenance: {result['error']['data']}")

    # Returning maintenance ID
    return result['result']['maintenanceids'][0]

# Main function
def main():
    parser = argparse.ArgumentParser(description="Create Zabbix maintenance for one or more hosts")
    parser.add_argument("--host", required=True, help="Comma-separated hostnames or * for all hosts")
    parser.add_argument("-t", "--time", required=True, help="Maintenance duration (e.g., '1h', '30m')")

    args = parser.parse_args()

    # If * is provided, fetch all host IDs
    if args.host == '*':
        print("Fetching all hosts...")
        hosts = get_all_host_ids()
        host_ids = list(hosts.values())
        print(f"Putting all hosts into maintenance: {', '.join(hosts.keys())}")
    else:
        # Split the comma-separated hostnames
        host_names = args.host.split(',')
        host_ids = []

        for host_name in host_names:
            host_name = host_name.strip()  # Remove any leading/trailing whitespace
            if not host_name:
                continue  # Skip empty hostnames

            host_id = get_host_id(host_name)
            host_ids.append(host_id)
            print(f"Found host {host_name} with ID: {host_id}")

    # Step 1: Parse the duration argument
    duration_str = args.time
    try:
        duration_seconds = parse_time_arg(duration_str)

        # Step 2: Create maintenance for the selected hosts
        maintenance_id = create_maintenance(host_ids, duration_seconds)

        # Step 3: Print the maintenance ID and the hosts involved
        print(f"Successfully created maintenance for the selected hosts with:")
        print(f"- Maintenance ID: {maintenance_id}")
        print(f"Duration: {duration_str}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
