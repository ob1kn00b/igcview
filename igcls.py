import argparse
import glob
from tabulate import tabulate
from libigc import Flight
from pathlib import Path
import datetime
import os


def format_duration(seconds):
    """Format duration in seconds to HH:MM:SS
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

def get_max_alt(flight):
    """Determine the highest altitude for all altitudes of all fixes
    """
    max_alt = max(fix.alt for fix in flight.fixes) if flight.fixes else 0
    return max_alt

def read_pilot_data(file_path):
    """Read IGC header data and extract specific fields.
    Returns: List of header data
    """
    # Initialize variables for each field
    device = "N/A"
    firmware = "N/A"
    sensor = "N/A"
    pilot = "N/A"
    site = "N/A"
    compclass = "N/A"
    glider = "N/A"
    gpsdatum = "N/A"
    pressuredatum = "N/A"   #ISA is International Standard Atmosphere (1013 hPa )
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Stop processing when we leave header section
                if not line.startswith('H'):
                    continue
                    
                if ':' in line:
                    key, value = line.split(':', 1)
                    value = value.strip()
                    
                    # Assign to corresponding variable using match-case
                    match key:
                        case 'HFFTYFRTYPE':
                            device = value
                        case 'HFRFWFIRMWAREVERSION':
                            firmware = value
                        case 'HFPRSPRESSALTSENSOR':
                            sensor = value
                        case 'HFPLTPILOTINCHARGE':
                            pilot = value
                        case 'HOSITSite':
                            site = value
                        case 'HOCCLCOMPETITION CLASS':
                            compclass = value
                        case 'HFGTYGLIDERTYPE':
                            glider = value
                        case 'HODTM100GPSDATUM':
                            gpsdatum = value
                        case 'HFALPALTPRESSURE':
                            pressuredatum = value
    
    except Exception as e:
        # Log error but still return partial data
        print(f"Error reading header: {e}")
        
    # Assemble variables into list
    header_data = [
        pilot,
        glider,
        compclass,
        site,
        device,
        sensor,
        firmware,
        gpsdatum,
        pressuredatum
    ]
    
    return header_data

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Process IGC flight files.')
    parser.add_argument('-f', '--files', nargs='*', help='List of IGC files to process')
    parser.add_argument('-l', '--long', action='store_true', help='Show detailed thermals and glides')
    args = parser.parse_args()
    
    # Determine which files to process
    if args.files:
        # Filter out non-existent files but keep existing ones
        existing_files = []
        missing_files = []
        
        for f in args.files:
            if os.path.exists(f):
                existing_files.append(f)
            else:
                missing_files.append(f)
        
        # Warn about missing files but continue with existing ones
        if missing_files:
            print(f"Warning: The following files were not found and will be skipped: {', '.join(missing_files)}")
        
        if not existing_files:
            print("No existing files to process")
            return
            
        igc_files = existing_files

    else:
        # Default to all IGC files in current directory
        igc_files = glob.glob("*.igc")
        if not igc_files:
            print("No IGC files found in current directory")
            return
    
    for file_path in igc_files:
        try:
            flight = Flight.create_from_file(file_path)
            pilot_data = read_pilot_data(file_path)
            #Extract the filename to use in the output table
            filename = Path(file_path).name

        except Exception as e:
            #If there is an exception regarding the file, then put the file path, error status and the exception string in to the flights table
            flight_data = [
                file_path,
                "Exception",
                "",
                "",
                "",
                "",
                "",
                "",
                str(e)
            ]

            #If there was an exception, print the file and exception, then move on to the next file
            headers = ["File", "Status", "Takeoff", "Landing", "Duration", "Max Alt (m)", "Thermals", "Glides", "Notes/Exception"]
            print(tabulate(flight_data, headers=headers, tablefmt="grid"))
            continue

        # Extract and format flight details
        if flight.valid:

            #Get flight takeoff and landing as datetime objects
            takeoff_dt = datetime.datetime.fromtimestamp(flight.takeoff_fix.timestamp)
            landing_dt = datetime.datetime.fromtimestamp(flight.landing_fix.timestamp)

            # Calculate and format flight duration
            duration = landing_dt - takeoff_dt
            total_seconds = duration.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"  
            # Format takeoff and landing times as UK date/time: DD/MM/YYYY HH:MM:SS
            takeoff = takeoff_dt.strftime("%d/%m/%Y %H:%M:%S")
            landing = landing_dt.strftime("%d/%m/%Y %H:%M:%S")

            #Calculate the max altitude for this flight
            max_alt=get_max_alt(flight)
            
            #Get the thermal and glide counts
            thermals = len(flight.thermals)
            glides = len(flight.glides)

            #Get any notes for the flight
            notes = ""

        else:
            #Flight data is invalid, so set some default values for the missing data
            takeoff = "N/A"
            landing = "N/A"
            thermals = 0
            glides = 0
            notes = flight.notes
            duration_str = "N/A"
            max_alt = "N/A"

        #Set data into the flight table to print out. The contents of which will change depending on whether the file data is valid or invalid above
        flight_data = [
            filename,
            "Valid" if flight.valid else "Invalid",
            takeoff,
            landing,
            duration_str,
            max_alt,
            thermals,
            glides,
            notes
        ]

        #Print file and flight details
        flight_headers = ["File", "Status", "Takeoff", "Landing", "Duration", "Max Alt (m)", "Thermals", "Glides", "Notes"]
        print(tabulate([flight_data], headers=flight_headers,tablefmt="grid"))

        # Print pilot and device details
        pilot_headers = ["Pilot", "Glider", "Class", "Site", "Device", "Sensor", "Firmware", "GPS Datum", "Pressure Datum"]
        table = tabulate([pilot_data], headers=pilot_headers,tablefmt="grid")
        for line in table.split('\n'):
            print('\t' + line)


        #If only flight data is required or the flight is not valid, skip thermals/glides and continue to the next file/flight  
        if not args.long or not flight.valid:
            continue
                
        # Otherwise determine and print this flight's thermals table
        thermal_data = []
        if flight.thermals:
            for thermal in flight.thermals:
                start_dt = datetime.datetime.fromtimestamp(thermal.enter_fix.timestamp)
                end_dt = datetime.datetime.fromtimestamp(thermal.exit_fix.timestamp)
                duration_sec = thermal.time_change()
                alt_gain = thermal.alt_change()
                avg_vario = thermal.vertical_velocity()
                
                thermal_data.append([
                    start_dt.strftime("%d/%m/%Y %H:%M:%S"),
                    end_dt.strftime("%d/%m/%Y %H:%M:%S"),
                    format_duration(duration_sec),
                    f"{alt_gain:.1f}",
                    f"{avg_vario:.2f}"
                ])
            
            if thermal_data:
                print("\n\tThermals:")
                thermal_headers = ["Start Time", "End Time", "Duration", "Alt Gain (m)", "Avg Vario (m/s)"]
                table = tabulate(thermal_data, headers=thermal_headers, tablefmt="grid")
                for line in table.split('\n'):
                    print('\t\t' + line)
            else:
                print("\n\tNo thermals found")
            
        # Otherwise determine and print this flight's glides table
        glide_data = []
        if flight.glides:
            for glide in flight.glides:
                start_dt = datetime.datetime.fromtimestamp(glide.enter_fix.timestamp)
                end_dt = datetime.datetime.fromtimestamp(glide.exit_fix.timestamp)
                duration_sec = glide.time_change()
                distance = glide.track_length
                avg_speed = glide.speed()
                glide_ratio = glide.glide_ratio()
                
                glide_data.append([
                    start_dt.strftime("%d/%m/%Y %H:%M:%S"),
                    end_dt.strftime("%d/%m/%Y %H:%M:%S"),
                    format_duration(duration_sec),
                    f"{distance:.2f}",
                    f"{avg_speed:.2f}",
                    f"{glide_ratio:.2f}"
                ])
            
            if glide_data:
                print("\n\tGlides:")
                glide_headers = ["Start Time", "End Time", "Duration", "Distance (km)", "Avg Speed (km/h)", "Glide Ratio"]
                table = tabulate(glide_data, headers=glide_headers, tablefmt="grid")
                for line in table.split('\n'):
                    print('\t\t' + line)
            else:
                print("\n\tNo glides found")
        
        # Add space between flights
        print()


if __name__ == "__main__":
    main()
