import os
import psutil
from flask import jsonify, render_template_string
from groq_system_functs import *


def get_function_names_from_file(file_path):
    file_path = clean_path(file_path)
    base_directory = project_root_get()
    full_path = os.path.join(base_directory, file_path)

    # Check for unauthorized access
    if not os.path.commonpath([full_path, base_directory]) == base_directory:
        print("DEBUG: Unauthorized path detected")  # Debug print
        return "Access denied: Unauthorized path.", 403

    try:
        # Verify if the path is a file
        if os.path.isfile(full_path):
            with open(full_path, 'r') as file:
                lines = file.readlines()

            # Prepare the content for rendering
            output_lines = []
            for index, line in enumerate(lines):
                if line.strip().startswith("def ") or line.strip().startswith("# Protocol:"):
                    leading_spaces = ' ' * (len(str(len(lines))) - len(str(index + 1)))  # Calculate leading spaces
                    output_lines.append(f"{leading_spaces}{index + 1}: {line}")

            # Template string for the HTML response
            html_template = """{{ content }}"""
            content = "".join(output_lines)
            return jsonify({"function_in_file": render_template_string(html_template, content=content)})

        else:
            print("DEBUG: The specified path is not a file.")  # Debug print
            return "The specified path is not a file.", 400

    except FileNotFoundError:
        print("DEBUG: FileNotFoundError")  # Debug print
        return "The specified file does not exist.", 404
    except PermissionError:
        print("DEBUG: PermissionError")  # Debug print
        return "Permission denied: Unable to access the file.", 403
    except Exception as err:
        print(f"DEBUG: Exception occurred: {err}")  # Debug print
        return str(err), 500


def get_whole_function_from_file(file_path, function_name):

    file_path = clean_path(file_path)
    base_directory = project_root_get()
    full_path = os.path.join(base_directory, file_path)

    # Check for unauthorized access
    if not os.path.commonpath([full_path, base_directory]) == base_directory:
        print("DEBUG: Unauthorized path detected")  # Debug print
        return "Access denied: Unauthorized path.", 403

    try:
        # Verify if the path is a file
        if os.path.isfile(full_path):
            with open(full_path, 'r') as file:
                lines = file.readlines()

            # Prepare the content for rendering
            output_lines = []
            function_found = False
            indentation_level = None

            for index, line in enumerate(lines):
                stripped_line = line.strip()

                # Check if the line starts with the function definition
                if stripped_line.startswith(f"def {function_name}"):
                    # No comments.
                    if not stripped_line.startswith("#"):
                        function_found = True
                        indentation_level = len(line) - len(line.lstrip())
                        output_lines.append(f"{index + 1}: {line}")

                # If the function has been found, continue to capture its body
                elif function_found:
                    current_indentation = len(line) - len(line.lstrip())

                    # Stop capturing if we encounter a line with 0 indentation, but only if the line is not empty
                    if current_indentation == 0 and stripped_line != '':
                        break

                    output_lines.append(f"{index + 1}: {line}")

            # Template string for the HTML response
            html_template = """{{ content }}"""
            content = "".join(output_lines)
            return jsonify({"function_in_file": render_template_string(html_template, content=content)})

        else:
            print("DEBUG: The specified path is not a file.")  # Debug print
            return "The specified path is not a file.", 400

    except FileNotFoundError:
        print("DEBUG: FileNotFoundError")  # Debug print
        return "The specified file does not exist.", 404
    except PermissionError:
        print("DEBUG: PermissionError")  # Debug print
        return "Permission denied: Unable to access the file.", 403
    except Exception as err:
        print(f"DEBUG: Exception occurred: {err}")  # Debug print
        return str(err), 500


def file_view(file_path):
    file_path = clean_path(file_path)
    base_directory = project_root_get()
    full_path = os.path.join(base_directory, file_path)

    # Check for unauthorized access
    if not os.path.commonpath([full_path, base_directory]) == base_directory:
        print("DEBUG: Unauthorized path detected")  # Debug print
        return "Access denied: Unauthorized path.", 403

    try:
        # Verify if the path is a file
        if os.path.isfile(full_path):
            with open(full_path, 'r') as file:
                lines = file.readlines()

            # Prepare the content for rendering
            output_lines = []
            for index, line in enumerate(lines):
                leading_spaces = ' ' * (len(str(len(lines))) - len(str(index + 1)))  # Calculate leading spaces
                output_lines.append(f"{leading_spaces}{index + 1}: {line}")

            # Template string for the HTML response
            html_template = """{{ content }}"""
            content = "".join(output_lines)
            return jsonify({"file_contents": render_template_string(html_template, content=content)})

        else:
            print("DEBUG: The specified path is not a file.")  # Debug print
            return "The specified path is not a file.", 400

    except FileNotFoundError:
        print("DEBUG: FileNotFoundError")  # Debug print
        return "The specified file does not exist.", 404
    except PermissionError:
        print("DEBUG: PermissionError")  # Debug print
        return "Permission denied: Unable to access the file.", 403
    except Exception as err:
        print(f"DEBUG: Exception occurred: {err}")  # Debug print
        return str(err), 500


def git_update():
    try:
        os.system("git pull origin main")
        return jsonify({"vbox": "Success! The function has been updated."})
    
    except Exception as e:
        return jsonify({"vbox": f"Error: {str(e)}"})


def get_system_status():
    # Load up python tools to check for memory, CPU, and disk usage.
    # Call psutil.cpu_percent twice to get accurate CPU usage
    psutil.cpu_percent(interval=1)
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    disk_usage = psutil.disk_usage('/')

    """
    status = {
        "cpu_usage": cpu_usage,
        "memory_total": memory_info.total,
        "memory_used": memory_info.used,
        "memory_free": memory_info.free,
        "disk_total": disk_usage.total,
        "disk_used": disk_usage.used,
        "disk_free": disk_usage.free,
    }
    """

    # Word this in English for the user. Inlucde percetages as well as byte values (MB/GB)
    return f"The system is currently using {cpu_usage}% of the CPU. The memory usage is {memory_info.percent}%. The disk usage is {disk_usage.percent}%. The system has { round(memory_info.total / 1024 / 1024, 2) } MB of memory and { round(disk_usage.total / 1024 / 1024 / 1024, 2) } GB of disk space."


def record_a_user_like():
    return "The user likes this function."