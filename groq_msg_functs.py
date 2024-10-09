import tiktoken
from groq_db_functs import *
from groq_system_functs import *
from groq_api_functs import *
from groq_protocols import *


def get_messages_lengths(conv_id = 0):
    messages_data = sql("""SELECT * FROM groq_messages
    WHERE conv_id = %s
    ORDER BY msg_created, msg_id;""", (conv_id, ))

    messages = []
    for message in messages_data:
        messages.append(message["msg_content"])
    
    return "".join(messages)


def get_token_count(content):

    dict_str = str(content)
    enc = tiktoken.encoding_for_model("gpt-4")
    disallowed_special = enc.special_tokens_set - {'<|endoftext|>'}
    
    # Tokenize and get token count
    tokens = enc.encode(dict_str, disallowed_special=disallowed_special)
    token_count = len(tokens)
    return token_count


def get_initial_system_messages():
    # Add the final system messages to include the time and date.
    tell_time_message = tell_time()

    current_weather = weather_get()

    # System status
    system_status = get_system_status()


    message = {
        "role": "system",
        "content": f"{tell_time_message} {current_weather} {system_status}",
    }

    return message


def format_db_messages(messages):
    formatted_messages = []
    token_count = 0
    for message in messages:
        formatted_messages.append({
            "role": message["msg_role"],
            "content": message["msg_content"],
        })
        token_count += get_token_count(message['msg_content'])
    return (formatted_messages, token_count)


