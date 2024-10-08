def project_root_get():
    return "/var/www/groq_chat"


def clean_path(path):
    return path.lstrip('/').replace(project_root_get(), '').lstrip('/')

