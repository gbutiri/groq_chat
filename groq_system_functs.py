def project_root_get():
    return "/var/www/groq_chat"


def clean_path(path):
    return path.lstrip('/').replace(project_root_get(), '').lstrip('/')


def print_debug_line(message, color="red"):

    if color == "red":
        color_start = "\033[91m"
        color_end = "\033[0m"
    elif color == "green":
        color_start = "\033[92m"
        color_end = "\033[0m"
    elif color == "yellow":
        color_start = "\033[93m"
        color_end = "\033[0m"
    elif color == "blue":
        color_start = "\033[94m"
        color_end = "\033[0m"
    elif color == "purple":
        color_start = "\033[95m"
        color_end = "\033[0m"
    elif color == "cyan":
        color_start = "\033[96m"
        color_end = "\033[0m"
    elif color == "white":
        color_start = "\033[97m"
        color_end = "\033[0m"
    else:
        color_start = ""
        color_end = ""

    print(f"{color_start} -- DEBUG: {message}!{color_end}")

    
