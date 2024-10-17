import json
from flask import render_template, request, jsonify, Blueprint
from groq_db_functs import sql


tool_bp = Blueprint('tool_bp', __name__)


@tool_bp.route("/see-tools-page", methods=["GET"])
def see_tools_page():
    tools = sql("""SELECT * FROM groq_tools 
                LEFT JOIN groq_tool_types USING(tool_type_id) 
                ORDER BY tool_id;""")
    
    for tool in tools:

        tool['parameters'] = sql("""SELECT * FROM groq_tool_parameters WHERE tool_id = %s;""", (tool['tool_id'], ))
    
    return render_template("tools.html", tools=tools)


@tool_bp.route("/see-tool/<tool_id>", methods=["GET"])
def see_tool(tool_id):
    tool = sql("""SELECT * FROM groq_tools 
                LEFT JOIN groq_tool_types USING(tool_type_id) 
                WHERE tool_id = %s;""", (tool_id, ))

    tool_types = sql("""SELECT * FROM groq_tool_types;""")
    tool_params = sql("""SELECT * FROM groq_tool_parameters WHERE tool_id = %s;""", (tool_id, ))

    return render_template("tool.html", tool=tool[0], tool_types=tool_types, tool_params=tool_params)


@tool_bp.route("/show-new-tool-type-page", methods=["POST"])
def show_new_tool_type_page():
    tool_types = sql("""SELECT * FROM groq_tool_types;""")

    return jsonify({
        "vbox": render_template("new-tool-type.html", tool_types=tool_types)
    })


@tool_bp.route("/show-new-parameter-page/<tool_id>", methods=["POST"])
def show_new_parameter_page(tool_id):

    return jsonify({
        "vbox": render_template("new-parameter.html", tool_id=tool_id)
    })


@tool_bp.route("/add-tool-type", methods=["POST"])
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


@tool_bp.route("/add-tool-parameter/<tool_id>", methods=["POST"])
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


@tool_bp.route("/remove-tool-parameter/<tool_param_id>", methods=["POST"])
def remove_tool_parameter(tool_param_id):

    tool_param = sql("""SELECT * FROM groq_tool_parameters WHERE tool_param_id = %s;""", (tool_param_id, ))

    sql("""DELETE FROM groq_tool_parameters WHERE tool_param_id = %s;""", (tool_param_id, ))

    all_tool_params = sql("""SELECT * FROM groq_tool_parameters WHERE tool_id = %s;""", (tool_param[0]['tool_id'], ))

    html_out = render_template("tool_param_list.html", tool_params=all_tool_params)

    return jsonify({
        "htmls": {
            "#tool_parameter": html_out,
        },
    })


@tool_bp.route("/add-groq-tool", methods=["POST"])
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


@tool_bp.route('/update-groq-tool/<tool_id>', methods=["POST"])
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


def get_tools():
    # This function is to mimic the list returned inside the get_tools() function.

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

    print("-- DEBUG: tool_list: ", tool_list)

    # Convert the generated object into a JSON friendly object.
    # tool_list = json.dumps(tool_list)
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
