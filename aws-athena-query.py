import boto3
import time
import json
import os

# --- Constants ---
DATABASE_NAME = 'your_glue_database_name' # Replace with your Glue Database Name
TABLE_NAME = 'your_glue_table_name'       # Replace with your Glue Table Name

# ---> DEFINE THE COLUMNS YOU WANT TO SELECT HERE <---
# Replace with the actual column names you need from your Athena table
REQUIRED_COLUMNS = ['column_name_1', 'column_name_5', 'another_column']

# Replace with your S3 bucket and prefix for Athena query results
# e.g., 's3://your-athena-query-results-bucket/results/'
ATHENA_OUTPUT_LOCATION = 's3://your-athena-results-bucket/path/'
QUERY_TIMEOUT_SECONDS = 300 # Max time to wait for the query to finish
POLL_INTERVAL_SECONDS = 2   # How often to check query status

# --- Validate Configuration ---
if 'your_glue_database_name' == DATABASE_NAME or \
   'your_glue_table_name' == TABLE_NAME:
    print("ERROR: Please update DATABASE_NAME and TABLE_NAME constants.")
    exit(1)

if not REQUIRED_COLUMNS:
    print("ERROR: REQUIRED_COLUMNS list cannot be empty. Please specify columns to select.")
    exit(1)

if 'your-athena-results-bucket' in ATHENA_OUTPUT_LOCATION:
    print("ERROR: Please update the ATHENA_OUTPUT_LOCATION constant with your S3 bucket path.")
    exit(1)
if not ATHENA_OUTPUT_LOCATION.endswith('/'):
    ATHENA_OUTPUT_LOCATION += '/'
    print(f"INFO: Added trailing slash to ATHENA_OUTPUT_LOCATION: {ATHENA_OUTPUT_LOCATION}")


# --- Construct the Query ---
# Create the SELECT clause with double-quoted column names
select_clause = ", ".join([f'"{col}"' for col in REQUIRED_COLUMNS])

# Using f-string to safely include table and database names
# IMPORTANT: Column names are from the REQUIRED_COLUMNS constant, assumed safe.
QUERY_STRING = f'SELECT {select_clause} FROM "{DATABASE_NAME}"."{TABLE_NAME}";'
# Example with a limit:
# QUERY_STRING = f'SELECT {select_clause} FROM "{DATABASE_NAME}"."{TABLE_NAME}" LIMIT 100;'


def run_athena_query_specific_columns():
    """
    Runs an Athena query for specific columns and returns results as a list of dictionaries.
    """
    client = boto3.client('athena')

    print(f"Starting Athena query on {DATABASE_NAME}.{TABLE_NAME} for specific columns...")
    print(f"Query: {QUERY_STRING}")
    print(f"Output Location: {ATHENA_OUTPUT_LOCATION}")

    try:
        # Start the query execution
        response = client.start_query_execution(
            QueryString=QUERY_STRING,
            QueryExecutionContext={
                'Database': DATABASE_NAME
            },
            ResultConfiguration={
                'OutputLocation': ATHENA_OUTPUT_LOCATION,
            }
        )

        query_execution_id = response['QueryExecutionId']
        print(f"Query Execution ID: {query_execution_id}")

        # Poll for query completion
        start_time = time.time()
        while time.time() - start_time < QUERY_TIMEOUT_SECONDS:
            stats = client.get_query_execution(QueryExecutionId=query_execution_id)
            status = stats['QueryExecution']['Status']['State']

            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                print(f"Query finished with status: {status}")
                break
            else:
                print(f"Query status: {status}. Waiting...")
                time.sleep(POLL_INTERVAL_SECONDS)
        else:
            # Timeout reached
            print(f"ERROR: Query timed out after {QUERY_TIMEOUT_SECONDS} seconds.")
            return None, "Query timed out"

        # Check final status
        if status == 'FAILED':
            reason = stats['QueryExecution']['Status'].get('StateChangeReason', 'Unknown reason')
            print(f"ERROR: Query Failed. Reason: {reason}")
            return None, f"Query Failed: {reason}"
        if status == 'CANCELLED':
            print("ERROR: Query was cancelled.")
            return None, "Query Cancelled"

        # --- Process results if SUCCEEDED ---
        print("Query Succeeded. Fetching results...")
        results_paginator = client.get_paginator('get_query_results')
        results_iter = results_paginator.paginate(
            QueryExecutionId=query_execution_id,
            PaginationConfig={'PageSize': 1000}
        )

        data_rows = []
        column_names = []
        is_first_page = True

        for results_page in results_iter:
            rows = results_page['ResultSet']['Rows']

            # Get column names from the first row of the first page
            # These should match REQUIRED_COLUMNS if the query is correct
            if is_first_page:
                if not rows:
                    print("Warning: Query returned no data.")
                    return [], None # Return empty list, no error
                column_row = rows[0]
                column_names = [col.get('VarCharValue', '') for col in column_row['Data']]
                print(f"Columns returned by Athena: {column_names}")

                # Basic check if returned columns match requested columns (order might differ)
                if set(column_names) != set(REQUIRED_COLUMNS):
                     print("Warning: Returned columns differ from requested columns. This might indicate an issue.")
                     print(f"Requested: {REQUIRED_COLUMNS}")
                     print(f"Returned: {column_names}")
                     # Proceeding anyway, using headers returned by Athena

                data_rows_in_page = rows[1:] # Skip header row
                is_first_page = False
            else:
                data_rows_in_page = rows

            # Convert rows to dictionaries using the actual headers from Athena
            for row in data_rows_in_page:
                values = [field.get('VarCharValue', None) for field in row['Data']]
                # Ensure we don't have more values than headers (can happen with schema evolution issues)
                record = dict(zip(column_names, values[:len(column_names)]))
                data_rows.append(record)

        print(f"Successfully fetched {len(data_rows)} data rows.")
        return data_rows, None # Return data and no error

    except client.exceptions.InvalidRequestException as e:
        print(f"ERROR: Invalid Request. Check database/table/column names and S3 path.")
        print(e)
        return None, f"Invalid Request: {e}"
    except client.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        error_message = e.response.get("Error", {}).get("Message")
        print(f"ERROR: An AWS Client error occurred: {error_code} - {error_message}")
        print(e)
        return None, f"AWS Client Error: {error_code} - {error_message}"
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return None, f"Unexpected Error: {e}"


# --- Main execution ---
if __name__ == "__main__":
    results_list, error = run_athena_query_specific_columns()

    if error:
        print(f"\nScript finished with error: {error}")
    elif results_list is not None:
        print("\n--- Constructing JSON String ---")
        # Convert the list of dictionaries to a JSON string
        # Use default=str to handle potential non-serializable types like dates/decimals
        # if they weren't explicitly cast in SQL. Athena usually returns strings.
        try:
             results_json_string = json.dumps(results_list, indent=2, default=str)
             print("\n--- Final JSON Output ---")
             print(results_json_string) # Print the constructed JSON string

             # Optional: Save to a file remains the same
             # output_filename = f"{DATABASE_NAME}_{TABLE_NAME}_selected_results.json"
             # with open(output_filename, 'w') as f:
             #    f.write(results_json_string)
             # print(f"\nResults also saved to {output_filename}")

        except Exception as e:
             print(f"\nERROR: Failed to convert results to JSON string: {e}")

    else:
         print("\nScript finished. No data returned or an error occurred before fetching.")