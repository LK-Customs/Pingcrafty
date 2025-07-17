import os
import json

def parse_text_files_to_json(input_folder, output_file='output.json'):
    """
    Parses all .txt files in a given folder, assuming each contains a JSON object.
    Combines them into a single JSON file.

    Args:
        input_folder (str): The path to the folder containing the .txt files.
        output_file (str): The name of the output JSON file.
    """
    all_data = []
    
    # Ensure the input folder exists
    if not os.path.isdir(input_folder):
        print(f"Error: Input folder '{input_folder}' not found.")
        return

    print(f"Scanning folder: {input_folder}")

    # Iterate over all files in the input folder
    for filename in os.listdir(input_folder):
        if filename.endswith(".txt"):
            filepath = os.path.join(input_folder, filename)
            print(f"Processing file: {filename}")
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Parse the content as JSON
                    data = json.loads(content)
                    # Add the filename as an identifier if needed
                    data['original_filename'] = filename 
                    all_data.append(data)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from {filename}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred while processing {filename}: {e}")

    # Write all collected data to a single JSON file
    try:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            json.dump(all_data, outfile, indent=4, ensure_ascii=False)
        print(f"\nSuccessfully parsed {len(all_data)} files and saved to {output_file}")
    except Exception as e:
        print(f"Error writing to output file {output_file}: {e}")

# --- Configuration ---
# IMPORTANT: Replace 'your_text_files' with the actual name of your folder
# where you unzipped the .txt files.
input_folder_name = 'ips.2025-07-12_01-09-40' 
output_json_name = 'parsed_data.json' # You can change the output file name

# Get the directory where the script is run
script_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the full path to your input folder
full_input_path = os.path.join(script_dir, input_folder_name)

# Run the parsing function
parse_text_files_to_json(full_input_path, output_json_name)