import csv
import requests
from datetime import datetime

'''
This is a one-off script to adjust the withdrawal dates for a group of
patients, based on a spreadsheet supplied by the research team.
If a row doesn't have a date in the 'Medidata_OFFSDT' column, the record
won't be touched, and this script will indicate that.
This is a clean-up task for 
https://movember.atlassian.net/browse/IRONN-210 .

Input file format:
user_id,value,name,research_study_id,acceptance_date,Medidata_OFFSDT,,Done
986,170-02-xxx,Duke Comprehensive Cancer Center,0,11/09/2023,8/30/2023,,
2740,170-02-yyy,Duke asdf,0,11/09/2023,8/1/2023,,
3442,170-02-zzz,Duke asdf,1,11/09/2023,2/10/2021,,
8888,170-02-uuu,Duke asdf,0,11/09/2023,not withdrawn,,
'''

# To run this, edit the values here, and then run w/out args.
my_token = "abc123"
serversansslash = "https://eproms-test.cirg.washington.edu"
inputfile = "new_withdraw_dates.csv"

# Function to convert date format from 'M/D/YYYY' to 'YYYY-MM-DDT00:00:00+00:00'
def convert_date_format(date_str):
    try:
        date_obj = datetime.strptime(date_str, '%m/%d/%Y')
        new_date_str = datetime.strftime(date_obj, '%Y-%m-%dT00:00:00+00:00')
        return new_date_str
    except ValueError:
        return None

# Function to process the csv file
def process_csv(file_path):
    with open(file_path, mode='r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            user_id_data = row['user_id']
            research_study_id_data = int(row['research_study_id'])
            new_date_data = convert_date_format(row['Medidata_OFFSDT'])
            if not new_date_data:
                print(f"Date format error for user_id {user_id_data}; the string was '{row['Medidata_OFFSDT']}'")
                continue

            print(f"Processing user_id {user_id_data}")
            headers = {
                'Authorization': f'Bearer {my_token}'
            }

            # First API call
            response = requests.get(
                f"{serversansslash}/api/user/{user_id_data}/consent",
                headers=headers
            )

            if response.status_code == 200:
                response_text = response.text
                #print(f"For user_id {user_id_data}, response.text:{response_text}")
                cas = response.json()
                consent_agreements = cas['consent_agreements']
                #consent_agreements = response.json
                # Find the matching consent agreement
                matching_agreement = next(
                    #(item for item in consent_agreements if item["research_study_id"] == 0 and item["status"] == "suspended"),
                    (item for item in consent_agreements if item["research_study_id"] == research_study_id_data and item["status"] == "suspended"),
                    None
                )

                if matching_agreement:
                    org_id_data = matching_agreement['organization_id']
                    json_data = {
                        "organization_id": org_id_data,
                        "acceptance_date": new_date_data,
                        "research_study_id": research_study_id_data 
                    }

                    # Second API call
                    response = requests.post(
                        f"{serversansslash}/api/user/{user_id_data}/consent/withdraw",
                        headers={**headers, 'Content-Type': 'application/json'},
                        json=json_data
                    )

                    if response.status_code != 200:
                        print(f"Error {response.status_code} for POST {serversansslash}/api/user/{user_id_data}/consent with data {json_data}")
                        continue

                    # Third API call
                    response = requests.get(
                        #f"{serversansslash}/api/patient/{user_id_data}/timeline?substudy=true&research_study_id=1&purge=true",
                        f"{serversansslash}/api/patient/{user_id_data}/timeline?substudy=true&research_study_id={research_study_id_data}&purge=true",
                        headers=headers
                    )

                    if response.status_code == 200:
                        print(f"Successfully processed user_id {user_id_data}")
                    else:
                        print(f"Error {response.status_code} for GET {serversansslash}/api/patient/{user_id_data}/timeline")
                else:
                    print(f"Error: More than one or no matching consent agreements found for user_id {user_id_data}")
            else:
                print(f"Error {response.status_code} for GET {serversanslash}/api/user/{user_id_data}/consent")

process_csv(inputfile)

