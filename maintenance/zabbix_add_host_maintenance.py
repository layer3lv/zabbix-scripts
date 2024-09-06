import requests
import time
import argparse
import re

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

# Function to get all host IDs from multiple groups
def get_host_ids_by_groups(group_names):
    host_ids = {}
    for group_name in group_names:
        payload = {
            "jsonrpc": "2.0",
            "method": "hostgroup.get",
            "params": {
                "output": ["groupid"],
                "filter": {
                    "name": [group_name]
                },
                "selectHosts": ["hostid", "host"]
            },
            "id": 1
        }

        response = requests.post(ZABBIX_URL, headers=HEADERS, json=payload)
        result = response.json()

        if "error" in result:
            raise Exception(f"Error fetching hosts from group {group_name}: {result['error']['data']}")

        if not result['result']:
            raise Exception(f"Host group {group_name} not found")

        hosts = result['result'][0]['hosts']
        for host in hosts:
            host_ids[host['host']] = host['hostid']  # Add to the dictionary, avoiding duplicates

    return host_ids

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
    parser = argparse.ArgumentParser(description="Create Zabbix maintenance for one or more hosts or a group of hosts")
    parser.add_argument("--host", help="Comma-separated hostnames or * for all hosts")
    parser.add_argument("--group", help="Comma-separated host group names to apply maintenance to all hosts in those groups")
    parser.add_argument("-t", "--time", required=True, help="Maintenance duration (e.g., '1h', '30m')")

    args = parser.parse_args()

    # Step 1: Parse the duration argument
    duration_str = args.time
    try:
        duration_seconds = parse_time_arg(duration_str)

        # Step 2: Determine if we are working with hosts, groups, or all hosts (*)
        if args.group:
            # Handle multiple groups by splitting the input
            group_names = [group.strip() for group in args.group.split(',')]
            print(f"Fetching hosts from groups: {', '.join(group_names)}...")
            hosts = get_host_ids_by_groups(group_names)
            host_ids = list(hosts.values())
            print(f"Putting all hosts in groups '{', '.join(group_names)}' into maintenance: {', '.join(hosts.keys())}")
        
        elif args.host == '*':
            print("Fetching all hosts...")
            hosts = get_all_host_ids()
            host_ids = list(hosts.values())
            print(f"Putting all hosts into maintenance: {', '.join(hosts.keys())}")
        
        elif args.host:
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

        else:
            raise Exception("You must specify either --host, --group, or * for all hosts.")

        # Step 3: Create maintenance for the selected hosts
        maintenance_id = create_maintenance(host_ids, duration_seconds)

        # Step 4: Print the maintenance ID and the hosts involved
        print(f"Successfully created maintenance for the selected hosts with:")
        print(f"- Maintenance ID: {maintenance_id}")
        print(f"Duration: {duration_str}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
