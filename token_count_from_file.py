import tiktoken

def get_token_count(content):
    dict_str = str(content)
    enc = tiktoken.encoding_for_model("gpt-4")
    disallowed_special = enc.special_tokens_set - {'<|endoftext|>'}
    
    # Tokenize and get token count
    tokens = enc.encode(dict_str, disallowed_special=disallowed_special)
    token_count = len(tokens)
    return token_count

def count_tokens_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        token_count = get_token_count(content)
        print(f"Token count: {token_count}")
    except FileNotFoundError:
        print(f"File {file_path} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Replace 'your_file.txt' with the actual file path
    file_path = 'git_diff_example.txt'
    count_tokens_from_file(file_path)
