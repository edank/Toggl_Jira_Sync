import requests
from base64 import b64encode
from datetime import datetime, timedelta
import math
import re
import json
import variables

def fetch_toggl_time_entries():
    # Set the headers
    auth_string = f"{variables.TOGGL_EMAIL}:{variables.TOGGL_PASSWORD}"

    encoded_auth_string = b64encode(auth_string.encode("ascii")).decode("ascii")
    headers = {
        "Authorization": f'Basic {encoded_auth_string}',
        "Content-Type": "application/json",
    }

    url = "https://api.track.toggl.com/api/v9/me/time_entries"

    # Get the current date
    today = datetime.now().date()

    # Date range to get tickets
    start_date = (today - timedelta(days=variables.DAYS_TO_GO_BACK)).strftime('%Y-%m-%d')
    end_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')

    print (f"Getting Toggl entries between {start_date} and {end_date}")


    # Set the query parameters
    params = {
        'start_date': start_date,
        'end_date': end_date
    }

    # GET Data
    data = requests.get(url, headers=headers, params=params)
    
    print(f"Got {len(data.json())} entries")

    return data.json()


def filter_toggl_entries(entries):
    print ("Filtering entries:")

    # combined_entries = {}
    filtered_entries = []
    
    for item in entries:
        tags = item['tags']

        # Only log tickets that aren't already in Jira
        if 'in-jira' not in tags and int(item['duration'] > 0):
            # print('description',item['description'] )

            # Get Jira ticket number
            description = item['description']
            ticket_number_match = re.match(r'^([a-zA-Z]+)-(\d+)', description) #e.g CR-123, CCB-1234

            if ticket_number_match:
                ticket_number = ticket_number_match.group(0)
            else:
                print(f"Ticket number doesn't exist for description: {description}")
                continue  # Skip to the next iteration of the loop

            print ("Processing:", ticket_number)

            # Get Date
            date = datetime.fromisoformat(item['start']).strftime('%Y-%m-%d')

            # key = f"{description}-{date}"
            new_item = {
                'description': description,
                'ticket_number': ticket_number,
                'date': date,
                'duration': math.ceil(item['duration'] / 900) * 15 * 60,  # Duration rounded up to the nearest 15 minutes in seconds
                'toggle_id': item['id'],
                'tags': item['tags']
            }
            filtered_entries.append(new_item)
    return list(filtered_entries)


def get_issue_id(ticket_key):
    api_url = f"{variables.JIRA_BASE_URL}/rest/api/3/issue/{ticket_key}"
    headers = {"Content-Type": "application/json"}
    auth = (variables.JIRA_API_USERNAME, variables.JIRA_API_TOKEN)

    # Send the GET request to retrieve the issue details
    response = requests.get(api_url, headers=headers, auth=auth)

    # Check the response status
    if response.status_code == 200:
        # Extract the issueId from the response
        issue_id = response.json()["id"]
        return issue_id
    else:
        print("Error retrieving issue details:", response.text)
        return None


def add_toggl_tag(entry_id, current_tags, tag_to_add):
    api_url = f"https://api.track.toggl.com/api/v9/workspaces/{variables.TOGGL_WORKSPACE_ID}/time_entries/{entry_id}"
    
    data = requests.put

    # Set the headers
    auth_string = f"{variables.TOGGL_EMAIL}:{variables.TOGGL_PASSWORD}"
    encoded_auth_string = b64encode(auth_string.encode("ascii")).decode("ascii")
    headers = {
        "Authorization": f"Basic {encoded_auth_string}",
        "Content-Type": "application/json"
    }

    # Payload to update the tags (currently overrides)
    current_tags.append(tag_to_add)
    payload = {
        "tags": current_tags,
        "project_id": variables.TOGGL_PROJECT_ID,
        "billable": True
    }

    # Send the PUT request to update the Toggl entry with the new tag
    response = requests.put(api_url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"Tag '{tag_to_add}' added to {entry_id}")
    else:
        print(f"Error adding tag to Toggl entry {entry_id}: {response.text}")


def log_tempo_worklog(entry):
    api_url = "https://api.tempo.io/4/worklogs"
    
    # Set the headers
    headers = {
        "Authorization": f"Bearer {variables.TEMPO_API_TOKEN}",
        "Content-Type": "application/json"
    }

    # Call API to get Issue ID
    issueId = get_issue_id(entry['ticket_number'])

    # Payload
    payload = {
        "attributes": [
            {
                "key": "_Dev_",
                "value": 1
            }
        ],
        "authorAccountId": variables.JIRA_ACCOUNT_ID,
        "description": entry['description'],
        "issueId": issueId,
        "startDate": entry['date'],
        "timeSpentSeconds": entry['duration'],
        "ticket_number": entry['ticket_number']
    }
    
    add_toggl_tag(entry['toggle_id'], entry['tags'], 'in-jira')

    # Send the POST request to log the work
    response = requests.post(api_url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"{entry['ticket_number']}: {entry['date']}, {int(entry['duration'])/3600}h")        
        
    else:
        print("Error updating worklog:", entry['ticket_number'], response.text)


def main():
    # Get toggl entries
    entries = fetch_toggl_time_entries()
    
    # Filter by only ones not already in jira
    filtered_entries = filter_toggl_entries(entries)
    
    # log in Jira (Tempo)
    for entry in filtered_entries:
        log_tempo_worklog(entry)


if __name__ == '__main__':
    main()