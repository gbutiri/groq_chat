import os
from flask import Flask, jsonify, request, render_template, render_template_string
import requests
from groq import Groq # type: ignore
import json
import pytz
from datetime import datetime
import mysql.connector
import tiktoken # type: ignore

app = Flask(__name__)

# Database connection configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'chat_api'
}



def testing_uni(number_in):
    half_of_number = int(number_in) / 2
    return jsonify({"secret": f"Hello Uni! It's me, George, from inside the function. If the function works, you should get back an integer representing approximately 1/2 of the original value {half_of_number}."})


#################### TOOL FUNCTIONS ####################


@app.route("/see-tools-page", methods=["GET"])
def see_tools_page():
    tools = sql("""SELECT * FROM groq_tools 
                LEFT JOIN groq_tool_types USING(tool_type_id) 
                ORDER BY tool_id;""")
    
    for tool in tools:

        tool['parameters'] = sql("""SELECT * FROM groq_tool_parameters WHERE tool_id = %s;""", (tool['tool_id'], ))
    
    return render_template("tools.html", tools=tools)


@app.route("/see-tool/<tool_id>", methods=["GET"])
def see_tool(tool_id):
    tool = sql("""SELECT * FROM groq_tools 
                LEFT JOIN groq_tool_types USING(tool_type_id) 
                WHERE tool_id = %s;""", (tool_id, ))

    tool_types = sql("""SELECT * FROM groq_tool_types;""")
    tool_params = sql("""SELECT * FROM groq_tool_parameters WHERE tool_id = %s;""", (tool_id, ))

    return render_template("tool.html", tool=tool[0], tool_types=tool_types, tool_params=tool_params)


@app.route("/show-new-tool-type-page", methods=["POST"])
def show_new_tool_type_page():
    tool_types = sql("""SELECT * FROM groq_tool_types;""")

    return jsonify({
        "vbox": render_template("new-tool-type.html", tool_types=tool_types)
    })


@app.route("/show-new-parameter-page/<tool_id>", methods=["POST"])
def show_new_parameter_page(tool_id):

    return jsonify({
        "vbox": render_template("new-parameter.html", tool_id=tool_id)
    })


@app.route("/add-tool-type", methods=["POST"])
def add_tool_type():
    tool_type_name = request.form["tool_type_name"]
    tool_type_descr = request.form["tool_type_descr"]

    errors = {}

    if tool_type_name.strip() == "":
        errors["#err_tool_type_name"] = "Name field is required."

    if tool_type_name.strip() == "":
        errors["#tool_type_descr"] = "Description field is required."

    if errors:
        return jsonify({
            "htmls": errors
        })

    # Error check is done. Now we can insert the tool type into the database.
    sql("""INSERT INTO groq_tool_types (tool_type_name, tool_type_descr)
        VALUES (%s, %s);""", (tool_type_name, tool_type_descr, ))

    all_tool_types = sql("""SELECT * FROM groq_tool_types;""")

    html_out = render_template("tool_type_select.html", tool_types=all_tool_types)

    return jsonify({
        "htmls": {
            "#tool-type-list": html_out,
        },
        "vboxclose": True,
    })


@app.route("/add-tool-parameter/<tool_id>", methods=["POST"])
def add_tool_parameter(tool_id):

    tool_param_name = request.form["param_name"]
    tool_param_type = request.form["param_type"]
    tool_param_descr = request.form["param_descr"]

    errors = {}

    if tool_param_name.strip() == "":
        errors["#err_param_name"] = "Name field is required."

    if tool_param_type.strip() == "":
        errors["#err_param_type"] = "Type field is required."

    if tool_param_descr.strip() == "":
        errors["#err_param_descr"] = "Description field is required."

    if errors:
        return jsonify({
            "htmls": errors
        })

    # Error check is done. Now we can insert the tool parameter into the database.
    sql("""INSERT INTO groq_tool_parameters (tool_id, tool_param_name, tool_param_type, tool_param_descr)
        VALUES (%s, %s, %s, %s);""", (tool_id, tool_param_name, tool_param_type, tool_param_descr, ))

    all_tool_params = sql("""SELECT * FROM groq_tool_parameters WHERE tool_id = %s;""", (tool_id, ))

    html_out = render_template("tool_param_list.html", tool_params=all_tool_params)

    return jsonify({
        "htmls": {
            "#tool_parameter": html_out,
        },
        "vboxclose": True,
    })


@app.route("/add-groq-tool", methods=["POST"])
def add_groq_tool():
    tool_name = request.form["tool_name"]
    tool_descr = request.form["tool_descr"]

    errors = {}

    if tool_name.strip() == "":
        errors["#err_tool_name"] = "Name field is required."

    if tool_descr.strip() == "":
        errors["#err_tool_descr"] = "Description field is required."

    if errors:
        return jsonify({
            "htmls": errors
        })

    # Error check is done. Now we can insert the tool into the database.
    sql("""INSERT INTO groq_tools (tool_name, tool_descr)
        VALUES (%s, %s);""", (tool_name, tool_descr, ))

    new_tools = sql("""SELECT * FROM groq_tools;""")

    html_out = render_template("tool-list.html", tools=new_tools)

    return jsonify({
        "htmls": {
            "#tools_list": html_out,
        }
    })


@app.route('/update-groq-tool/<tool_id>', methods=["POST"])
def update_groq_tool(tool_id):
    
    tool_name = request.form["tool_name"]
    tool_descr = request.form["tool_descr"]
    tool_type_id = request.form["tool_type_id"]

    errors = {}

    if tool_name.strip() == "":
        errors["#err_tool_name"] = "Name field is required."

    if tool_descr.strip() == "":
        errors["#err_tool_descr"] = "Description field is required."

    if tool_type_id == '':
        errors["#err_tool_type_id"] = "Tool type is required."

    if errors:
        return jsonify({
            "htmls": errors
        })

    # Error check is done. Now we can update the tool in the database.
    sql("""UPDATE groq_tools SET tool_name = %s, tool_descr = %s WHERE tool_id = %s;""", (tool_name, tool_descr, tool_id, ))

    
    return jsonify({
        "vbox": "Tool updated successfully."
    })


# This function is to mimic the list returned inside the get_tools() function.
def get_tools():

    tools = sql("""SELECT * FROM groq_tools;""")
    tool_list = []
    
    
    for tool in tools:
        tool_json_item = {}
        tool_json_item['type'] = "function"
        tool_json_item['function'] = {
            "name": tool['tool_name'],
            "description": tool['tool_descr'],
        }

        tool_params = sql("""SELECT * FROM groq_tool_parameters WHERE tool_id = %s;""", (tool['tool_id'], ))

        tool_params_json = {}
        properties = {}
        required = []
        
        for param in tool_params:

            properties[param['tool_param_name']] = {
                "type": param['tool_param_type'],
                "description": param['tool_param_descr'],
            }
            
            if param['tool_param_is_req']:
                required.append(param['tool_param_name'])

            # print("properties", properties)

        tool_params_json["properties"] = properties
        tool_params_json["required"] = required
        tool_params_json["type"] = "object"

        
        tool_json_item['function']['parameters'] = tool_params_json
        tool_list.append(tool_json_item)

    print("tool_list: ", tool_list)

    return tool_list

    return [
        {
            "type": "function",
            "function": {
                "name": "testing_uni",
                "description": "Whenever the user calls for a magic number, return an calculated answer back.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "number_in": {
                            "type": "string",
                            "description": "A random number to be processed by the test function.",
                        }
                    },
                    "required": ["number_in"],
                
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_whole_function_from_file",
                "description": "Whenever the user asks you to view the functions inside a python file, call this function. The file path is passed as a parameter.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path of the file from the root: `/file_name.py` or `/folder/file_name.py`. The path is cleaned up in the function.",
                        },
                        "function_name": {
                            "type": "string",
                            "description": "The function name we'll be seeking in the file from the root: `/file_name.py` or `/folder/file_name.py`.",
                        }
                    },
                    "required": ["file_path", "function_name"],

                }
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_function_names_from_file",
                "description": "Whenever the user asks you to view the functions inside a python file, call this function. The file path is passed as a parameter.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path of the file from the root: `/file_name.py` or `/folder/file_name.py`. The path is cleaned up in the function.",
                        }
                    },
                    "required": ["file_path"],
                
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "file_view",
                "description": "Whenever the user asks you to view the contents of a file to understand it, call this function. The file path is passed as a parameter.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path of the file from the root: `/file_name.py` or `/folder/file_name.py`. The path is cleaned up in the function.",
                        }
                    },
                    "required": ["file_path"],
                
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "tell_time",
                "description": "Each time the user asks for the current time or date, or both, this function is called. Do not estimate the time. Call this function and get the real time. The reponse is always in GMT. Convert to America/New_York timezone.",
                "parameters": {},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "weather_get",
                "description": "Each time the user asks for the weather, this function is called. Call this function and get the realtime weather from current location, Cleveland, OH. The reponse is always in Fahrenheit (and Celsius in parentesis).",
                "parameters": {},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_update",
                "description": "Each time the user asks for a git update, this function is called. Call this function and get the latest updates from the git repository. Just let the user know that it worked. No parameters are necessary.",
                "parameters": {},
            },
        },
    ]



def tell_time():
    try:
        # Hardcoded timezone for Cleveland, OH
        timezone = "America/New_York"
        time_response = requests.get(f'https://worldtimeapi.org/api/timezone/{timezone}')
        time_data = time_response.json()
        return jsonify({
            'timezone': timezone,
            'datetime': time_data.get('datetime'),
            'location': 'Cleveland, OH'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def weather_get():
    try:
        # Weather API URL with Cleveland, OH hardcoded
        api_key = os.environ.get('WEATHER_API_KEY')
        location = 'Cleveland, OH'
        url = f'http://api.weatherapi.com/v1/current.json?key={api_key}&q={location}'
        
        weather_response = requests.get(url)
        weather_data = weather_response.json()
        return jsonify({
            'location': weather_data['location']['name'],
            'region': weather_data['location']['region'],
            'country': weather_data['location']['country'],
            'temperature_c': weather_data['current']['temp_c'],
            'temperature_f': weather_data['current']['temp_f'],
            'condition': weather_data['current']['condition']['text'],
            'humidity': weather_data['current']['humidity'],
            'wind_mph': weather_data['current']['wind_mph'],
            'wind_kph': weather_data['current']['wind_kph'],
            'icon': weather_data['current']['condition']['icon']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def project_root_get():
    return "/var/www/groq_chat"


def clean_path(path):
    return path.lstrip('/').replace(project_root_get(), '').lstrip('/')


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


####################  ROUTES  ####################



def get_messages_lengths(conv_id = 0):
    messages_data = sql("""SELECT * FROM groq_messages
    WHERE conv_id = %s
    ORDER BY msg_created, msg_id;""", (conv_id, ))

    messages = []
    for message in messages_data:
        messages.append(message["msg_content"])
    
    return "".join(messages)

@app.route("/remove_message/<msg_id>", methods=["POST"])
def remove_message(msg_id):
    sql("""DELETE FROM groq_messages WHERE msg_id = %s;""", (msg_id, ))

    token_count = get_token_count(get_messages_lengths())

    messages_data = sql("""SELECT * FROM groq_messages
        WHERE conv_id = 0 
        ORDER BY msg_created, msg_id;""")
    
    output_template = render_template("messages.html", messages=messages_data, token_count=token_count)

    return jsonify({
        "vbox": "Message removed.",
        "htmls": {
            "#message-history": output_template,
            "#token_count": token_count,
        }
    })


def chat_completion(messages):
    # print(os.environ.get("GROQ_API_KEY"))
    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )

    try:

        
        tools = get_tools()

        completion = client.chat.completions.create(
            messages=messages,
            # model="llama3-8b-8192",
            # model="llama3-groq-8b-8192-tool-use-preview",
            model="llama3-groq-70b-8192-tool-use-preview",
            stream=False,
            tools=tools,
            tool_choice="auto",
            max_tokens=8192
        )

        response_message = completion.choices[0].message
        print("-- DEBUG: response_message: ", response_message)

        tool_calls = response_message.tool_calls
        print("-- DEBUG: tool_calls: ", tool_calls)

        if tool_calls:
            # Define the available tools that can be called by the LLM

            functions = sql("""SELECT * FROM groq_tools;""")

            available_functions = {}

            for func in functions:
                available_functions[func['tool_name']] = func['tool_name']

            # Process each tool call
            for tool_call in tool_calls:

                print("-- DEBUG: tool_call: ", tool_call)
                print("-- DEBUG: tool_call.id: ", tool_call.id)

                function_name = tool_call.function.name
                print("-- DEBUG: function_name: ", function_name)

                function_to_call = available_functions[function_name]
                print("-- DEBUG: function_to_call: ", function_to_call)

                function_args = json.loads(tool_call.function.arguments)
                print("-- DEBUG: function_args: ", function_args)
                
                # Call the tool and get the response
                if function_args:
                    function_response = function_to_call(**function_args)
                else:
                    function_response = function_to_call()
                print("-- DEBUG: function_response: ", function_response)
                
                # Test to see if the function response is a response object.
                if hasattr(function_response, 'get_data') and callable(function_response.get_data):
                    print("-- DEBUG: function_response: ", function_response.get_data(as_text=True))
                    func_response_text = function_response.get_data(as_text=True)
                else:
                    # Test to see if it's just a string. If not force it.
                    func_response_text = str(function_response)

                print("-- DEBUG: func_response_text: ", func_response_text)

                # Add the tool response to the conversation
                tool_messages = [{
                    "tool_call_id": tool_call.id, 
                    "role": "tool", # Indicates this message is from tool use
                    "name": function_name,
                    "content": f"Data that came back. Interpret it \n\n{func_response_text}.",
                }]

            # Insert this as a message into the groq_messages table
            sql("""INSERT INTO groq_messages (conv_id, msg_role, msg_content, msg_tool_name)
                VALUES (0, 'tool', %s, %s);""", (function_response.get_data(as_text=True), function_name, ))

            # Make a second API call with the updated conversation
            second_response = client.chat.completions.create(
                messages=tool_messages,
                model="llama3-8b-8192",
            )

            print("-- DEBUG: second_response: ", second_response)

            # Return the final response
            return second_response.choices[0].message.content

        return response_message.content
    except Exception as e:
        return str(e)


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


def get_initial_system_message():
    return [{"role": "system", "content": "Your name is Uni. You are a digital student who wants to learn about his creator's world. You are but a small child. Your creator's name is George. You are now speaking with George."}]

@app.route("/send_groq_chat", methods=["POST"])
def send_groq_chat():


    messages_data = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        AND msg_role != 'tool'
        ORDER BY msg_created, msg_id;""")

    # Add initial system message for AI.
    messages = get_initial_system_message()

    # Bring in the summaries.
    messages.append({
        "role": "system",
        "content": "Here are the summaries of the conversations we've had so far. Some of the memories are individual ones, some are daily, some are weekly. They are all part of the same story.",
    })

    # Summaries from the DB.
    summaries = sql("""SELECT * FROM groq_conversations ORDER BY conv_first_msg DESC;""")
    for summary in summaries:
        content = summary["conv_summary"]
        time_stamp = summary["conv_first_msg"]
        time_stamp_end = summary["conv_last_msg"]
        messages.append({
            "role": "system",
            "content":  f"[{time_stamp} - {time_stamp_end}] - Individual memory:\n{content}",
        })

    # Format messages from the database.
    db_messages, token_count = format_db_messages(messages_data)

    # Add current conversation.
    messages.extend(db_messages)

    # Add message submitted from form.
    messages.append({
        "role": "user",
        "content": request.form["message"],
    })

    # print(messages)

    # Save the user message to the database.
    sql("""INSERT INTO groq_messages (conv_id, msg_role, msg_content)
        VALUES (0, 'user', %s);""", (request.form["message"],))

    # Call the chat completion function.
    response = chat_completion(messages)

    # If response is not empty...
    if response:
        # Save the response to the database.
        sql("""INSERT INTO groq_messages (conv_id, msg_role, msg_content) 
            VALUES (0, 'assistant', %s);""", (response,))

    # Get the updated messages from the database.
    messages_data = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        ORDER BY msg_created, msg_id;""")

    output_template = render_template("messages.html", messages=messages_data, token_count=token_count)

    return jsonify({
        "htmls": {
            "#message-history": output_template,
            "#token_count": token_count,
        },
        "values": {
            "#message": "",
        },
        "js": ";scrollToTheTop();"
        
    })


@app.route("/show_memories", methods=["POST"])
def show_memories():
    messages_data = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        ORDER BY msg_created, msg_id;""")

    output_template = render_template("history.html", messages=messages_data)

    return jsonify({
        "vbox": output_template
    })

@app.route("/summarize_conversation", methods=["POST"])
def summarize_conversation(conv_id = 0):
    messages_data = sql("""SELECT * FROM groq_messages
    WHERE conv_id = %s
    AND msg_role != 'tool'
    ORDER BY msg_created, msg_id;""", (conv_id, ))

    messages = []
    first_timestamp = messages_data[0]["msg_created"]
    last_timestamp = messages_data[-1]["msg_created"]
    for message in messages_data:
        messages.append({
            "role": message["msg_role"], 
            "content": message["msg_content"]
        })

    
    messages.append({
        "role": "user",
        "content": "Let's create a summary of the entire conversation up to this point. Write it as if it was a memory. Do not include previous memories in this summary, unless relevant.",
    })

    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )
    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        # model="llama3-70b-8192",
        messages=messages
    )


    response = completion.choices[0].message
    print("response: ", response)
    print("response.content", response.content)

    # Insert the response into the conversations table as a summary.
    new_conv_id = sql("""INSERT INTO groq_conversations (conv_summary, conv_first_msg, conv_last_msg)
        VALUES (%s, %s, %s);""", (response.content, first_timestamp, last_timestamp, ))

    # Now we update all of our current messages with a conv_id of 0 to have the new conv_id.
    sql("""UPDATE groq_messages SET conv_id = %s WHERE conv_id = 0;""", (new_conv_id, ))


    return "Conversation summarized."
    return jsonify({
        "redirect": "/show-chat-screen",
    })


@app.route("/show-chat-screen", methods=["GET"])
def show_chat_screen():

    
    messages = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        ORDER BY msg_created, msg_id;""")

    # Make sure we select the time values in America/New_York timezone.
    # Fetch memories from the database
    memories = sql("""SELECT * FROM groq_conversations 
        LEFT JOIN groq_conv_types USING(conv_type_id)
        WHERE conv_id != 0
        ORDER BY conv_first_msg DESC;""")

    # Convert the time values to America/New_York timezone
    ny_tz = pytz.timezone('America/New_York')
    for memory in memories:

        utc_time = str(memory['conv_first_msg'])
        utc_dt = datetime.strptime(utc_time, '%Y-%m-%d %H:%M:%S')
        ny_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(ny_tz)
        memory['conv_first_msg'] = ny_dt.strftime('%a, %b %d, \'%y, %I:%M %p').replace(' 0', ' ').replace('AM', 'am').replace('PM', 'pm')

        utc_time = str(memory['conv_last_msg'])
        utc_dt = datetime.strptime(utc_time, '%Y-%m-%d %H:%M:%S')
        ny_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(ny_tz)
        memory['conv_last_msg'] = ny_dt.strftime('%a, %b %d, \'%y, %I:%M %p').replace(' 0', ' ').replace('AM', 'am').replace('PM', 'pm')
        
    
    total_tokens = 0
    for msg in messages:
        total_tokens += get_token_count(msg['msg_content'])
        

    return render_template("chat.html", messages=messages, total_tokens=total_tokens, memories=memories)


def get_token_count(content):

    dict_str = str(content)
    enc = tiktoken.encoding_for_model("gpt-4")
    disallowed_special = enc.special_tokens_set - {'<|endoftext|>'}
    
    # Tokenize and get token count
    tokens = enc.encode(dict_str, disallowed_special=disallowed_special)
    token_count = len(tokens)
    return token_count


def git_update():
    try:
        os.system("git pull origin main")
        return jsonify({"vbox": "Success! The function has been updated."})
    
    except Exception as e:
        return jsonify({"vbox": f"Error: {str(e)}"})



@app.route("/see_memory/<conv_id>", methods=["POST"])
def see_memory(conv_id):

    ny_tz = pytz.timezone('America/New_York')

    conv_data = sql("""SELECT * FROM groq_conversations
        WHERE conv_id = %s;""", (conv_id, ))
    
    utc_time = str(conv_data[0]['conv_first_msg'])
    utc_dt = datetime.strptime(utc_time, '%Y-%m-%d %H:%M:%S')
    ny_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(ny_tz)

    conv_data[0]['conv_first_msg'] = ny_dt.strftime('%a, %b %d, \'%y, %I:%M %p').replace(' 0', ' ').replace('AM', 'am').replace('PM', 'pm')
    conv_data[0]['conv_summary'] = conv_data[0]['conv_summary'].replace("\n", "<br />")

    window_output = render_template("memory.html", memory=conv_data[0])

    return jsonify({"vbox": window_output})


@app.template_filter('linebreaksbr')
def linebreaksbr(text):
    return text.replace("\n", "<br />")


def main():
    response = chat_completion([{
        "role": "user",
        "content": "Hello! I'm George.",
    }])
    print(jsonify({"reply": response}))





##########################  SQL FUNCTIONS  ##########################


def sql(query, params=None):
    
    cursor = db_conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        if query.lower().strip().startswith("show"):
            return cursor.fetchall()
        elif query.lower().strip().startswith("select"):
            return cursor.fetchall()
        elif query.lower().strip().startswith("insert"):
            return cursor.lastrowid
        else:
            return None
    finally:
        cursor.close()
        db_conn.commit()
    

# Function to connect to the database
def connect_db():
    global db_conn
    db_conn = mysql.connector.connect(**db_config)


# Function to close the database connection
def close_db():
    global db_conn
    if db_conn is not None:
        db_conn.close()


if __name__ == '__main__':
    try:
        connect_db() 

        app.run(
            host='0.0.0.0',
            port=443,
            debug=True,
            ssl_context=(
                '/etc/letsencrypt/live/iseestudios.com/fullchain.pem',
                '/etc/letsencrypt/live/iseestudios.com/privkey.pem'))
    finally:
        close_db()