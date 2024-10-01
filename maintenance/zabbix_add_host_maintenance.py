import requests
import time
import argparse
import re
import configparser
import os

# Load Zabbix configuration from the specified config file
def load_zabbix_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)

    zabbix_url = config.get('DEFAULT', 'ZABBIX_URL', fallback=None)
    api_token = config.get('DEFAULT', 'API_TOKEN', fallback=None)

    if not zabbix_url or not api_token:
        raise Exception("ZABBIX_URL and API_TOKEN must be set in the config file")

    return zabbix_url, api_token

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
def get_all_host_ids(zabbix_url, headers):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "host"]
        },
        "id": 1
    }

    response = requests.post(zabbix_url, headers=headers, json=payload)
    result = response.json()

    if "error" in result:
        raise Exception(f"Error fetching all hosts: {result['error']['data']}")

    hosts = result['result']
    return {host['host']: host['hostid'] for host in hosts}

# Function to get the host ID based on the host name
def get_host_id(zabbix_url, headers, host_name):
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

    response = requests.post(zabbix_url, headers=headers, json=payload)
    result = response.json()

    if "error" in result:
        raise Exception(f"Error fetching host ID for {host_name}: {result['error']['data']}")

    if result['result']:
        return result['result'][0]['hostid']
    else:
        raise Exception(f"Host {host_name} not found")

# Function to get all host IDs from multiple groups
def get_host_ids_by_groups(zabbix_url, headers, group_names):
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

        response = requests.post(zabbix_url, headers=headers, json=payload)
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
def create_maintenance(zabbix_url, headers, host_ids, duration):
    start_time = int(time.time())
    end_time = start_time + duration

    # Create a unique name by appending the current timestamp
    unique_name = f"Maintenance for selected hosts - {start_time}"

    # Step 1: Create maintenance with a unique name (timestamp)
    initial_payload = {
        "jsonrpc": "2.0",
        "method": "maintenance.create",
        "params": {
            "name": unique_name,
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

    response = requests.post(zabbix_url, headers=headers, json=initial_payload)
    result = response.json()

    if "error" in result:
        raise Exception(f"Error creating maintenance: {result['error']['data']}")

    # Step 2: Get the maintenance ID
    maintenance_id = result['result']['maintenanceids'][0]

    # Step 3: Update the maintenance name to include the maintenance ID
    updated_name = f"Maintenance for selected hosts - Maintenance ID:{maintenance_id}"
    update_payload = {
        "jsonrpc": "2.0",
        "method": "maintenance.update",
        "params": {
            "maintenanceid": maintenance_id,
            "name": updated_name
        },
        "id": 1
    }

    update_response = requests.post(zabbix_url, headers=headers, json=update_payload)
    update_result = update_response.json()

    if "error" in update_result:
        raise Exception(f"Error updating maintenance name: {update_result['error']['data']}")

    # Returning the updated maintenance ID
    return maintenance_id

# Function to list all maintenance tasks
def list_maintenance_tasks(zabbix_url, headers):
    payload = {
        "jsonrpc": "2.0",
        "method": "maintenance.get",
        "params": {
            "output": ["maintenanceid", "name", "active_since", "active_till"],
            "sortfield": "active_since",
            "sortorder": "DESC"
        },
        "id": 1
    }

    response = requests.post(zabbix_url, headers=headers, json=payload)
    result = response.json()

    if "error" in result:
        raise Exception(f"Error listing maintenance tasks: {result['error']['data']}")

    return result['result']

# Function to delete multiple maintenance tasks by their IDs
def delete_maintenance_tasks(zabbix_url, headers, maintenance_ids):
    payload = {
        "jsonrpc": "2.0",
        "method": "maintenance.delete",
        "params": maintenance_ids,  # Send a list of maintenance IDs to delete
        "id": 1
    }

    response = requests.post(zabbix_url, headers=headers, json=payload)
    result = response.json()

    if "error" in result:
        raise Exception(f"Error deleting maintenance tasks {maintenance_ids}: {result['error']['data']}")

    return result['result']['maintenanceids']

# Main function
def main():
    parser = argparse.ArgumentParser(
        description="Create, list, or delete Zabbix maintenance tasks for one or more hosts or groups.",
        epilog="""
Examples of usage:

  Single host:
    python zabbix_maintenance_new.py --config zbx_api.conf --host host1.example.com --time 1h

  List maintenance tasks:
    python zabbix_maintenance_new.py --config zbx_api.conf --list

  Delete multiple maintenance tasks:
    python zabbix_maintenance_new.py --config zbx_api.conf --delete 53,54
        """
    )
    parser.add_argument("--config", required=True, help="Path to the configuration file")
    parser.add_argument("--host", help="Comma-separated hostnames or * for all hosts")
    parser.add_argument("--group", help="Comma-separated host group names to apply maintenance to all hosts in those groups")
    parser.add_argument("--time", help="Maintenance duration (e.g., '1h', '30m')")
    parser.add_argument("--list", action="store_true", help="List all active maintenance tasks")
    parser.add_argument("--delete", help="Comma-separated maintenance IDs to delete")

    args = parser.parse_args()

    try:
        zabbix_url, api_token = load_zabbix_config(args.config)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}"
        }

        if args.list:
            # List all maintenance tasks
            tasks = list_maintenance_tasks(zabbix_url, headers)
            for task in tasks:
                start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(task['active_since'])))
                end_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(task['active_till'])))
                print(f"Maintenance ID: {task['maintenanceid']}, Name: {task['name']}, Start: {start_time}, End: {end_time}")
        
        elif args.delete:
            # Delete the specified maintenance tasks (comma-separated list)
            maintenance_ids = [maintenance_id.strip() for maintenance_id in args.delete.split(',')]
            deleted_ids = delete_maintenance_tasks(zabbix_url, headers, maintenance_ids)
            print(f"Deleted maintenance task(s) with ID(s): {', '.join(deleted_ids)}")

        elif args.time:
            # Create maintenance based on hosts or groups
            duration_seconds = parse_time_arg(args.time)

            if args.group:
                group_names = [group.strip() for group in args.group.split(',')]
                hosts = get_host_ids_by_groups(zabbix_url, headers, group_names)
                host_ids = list(hosts.values())
                print(f"Putting all hosts in groups '{', '.join(group_names)}' into maintenance.")
            
            elif args.host == '*':
                hosts = get_all_host_ids(zabbix_url, headers)
                host_ids = list(hosts.values())
                print("Putting all hosts into maintenance.")
            
            elif args.host:
                host_names = args.host.split(',')
                host_ids = [get_host_id(zabbix_url, headers, host_name.strip()) for host_name in host_names]
            
            else:
                raise Exception("You must specify either --host, --group, or * for all hosts.")

            maintenance_id = create_maintenance(zabbix_url, headers, host_ids, duration_seconds)
            print(f"Successfully created maintenance with ID: {maintenance_id}")

        else:
            raise Exception("You must specify either --list, --delete, or provide time for maintenance creation.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
