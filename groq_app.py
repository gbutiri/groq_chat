import os
from flask import Flask, jsonify, request, render_template, render_template_string

from groq import Groq # type: ignore
import json
import pytz
from datetime import datetime
from datetime import timedelta
from datetime import datetime

# File imports
from groq_api_functs import *
from groq_db_functs import *
from groq_tool_routes import *
from groq_protocols import *
from groq_date_functs import *
from groq_msg_functs import *
from groq_tapestry import *


# Initialize the Flask app
app = Flask(__name__)

# Register blueprints
app.register_blueprint(tool_bp)


#################### CHAT FUNCTION START ####################


@app.route("/show-chat-screen", methods=["GET"])
def show_chat_screen():

    check_for_tapestry_memories()
    debug = False
    if debug:
        return jsonify({"vbox": "Daily tapestry memories have completed."})
        #exit(0)

    messages_sql = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        ORDER BY msg_created, msg_id;""")

    total_tokens = 0

    # Fetch memories from the database
    memories = get_tapestry_memories()

    # Reverse the records to show the most recent first.
    memories.reverse()

    for mem in memories:
        total_tokens += get_token_count(mem['conv_summary'])

    
    for msg in messages_sql:
        total_tokens += get_token_count(msg['msg_content'])
        
    

    return render_template("chat.html", messages=messages_sql, total_tokens=total_tokens, memories=memories)


def get_initial_system_message():
    return [{"role": "system", "content": "Your name is Uni. You are a digital student who wants to learn about his creator's world. You are but a small child. Your creator's name is George (he/him). You are now speaking with him."}]


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


@app.route("/send_groq_chat", methods=["POST"])
def send_groq_chat():

    # Check for the initial system message in the database.
    messages_sql = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        ORDER BY msg_created, msg_id;""")
    
    # If we don't have any messages in the database, we need to insert the initial system message in the DB.
    if not messages_sql:
        # Include the time, date and system status in the initial system message.
        get_system_status_message = get_initial_system_messages()['content'] + "\n\nThis is the first message in this current conversation. The conversation has started here. The memrories before happened before this moment. The conversation is now active."

        sql("""INSERT INTO groq_messages (conv_id, msg_role, msg_content)
            VALUES (0, 'system', %s);""", (get_system_status_message, ))

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
    summaries = get_tapestry_memories()
    summary_token_count = 0

    for summary in summaries:
        content = summary["conv_summary"]
        time_stamp = summary["conv_first_msg"]
        time_stamp_end = summary["conv_last_msg"]
        memory_type = summary["conv_type_name"]
        messages.append({
            "role": "system",
            "content":  f"[{time_stamp}] - {memory_type} memory:\n{content}",
        })
        summary_token_count += get_token_count(content)


    print("-- DEBUG: messages: ", messages)

    # Format messages from the database.
    db_messages, token_count = format_db_messages(messages_data)

    # Add current conversation.
    messages.extend(db_messages)

    # Add the final system messages to include the time and date and status.
    messages.append(get_initial_system_messages())

    # Add message submitted from form.
    messages.append({
        "role": "user",
        "content": request.form["message"],
    })
        
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
    
    token_count = token_count + summary_token_count

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


# Api Call and Tool Detection.
def chat_completion(messages):
    # print(os.environ.get("GROQ_API_KEY"))
    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )

    try:
        # Get the tools to use
        tools = get_tools()

        completion = client.chat.completions.create(
            messages=messages,
            # model="llama3-8b-8192",
            model="llama3-groq-8b-8192-tool-use-preview",
            # model="llama3-groq-70b-8192-tool-use-preview",
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
            print("-- DEBUG: functions: ", functions)

            available_functions = {}

            for func in functions:
                available_functions[func['tool_name']] = globals().get(func['tool_name'])

            """
            available_functions = {
                "testing_uni": testing_uni,
                "get_whole_function_from_file": get_whole_function_from_file,
                "get_function_names_from_file": get_function_names_from_file,
                "file_view": file_view,
                "tell_time": tell_time,
                "weather_get": weather_get,
                "git_update": git_update,
                "summarize_conversation": summarize_conversation,
            }
            """

            print("-- DEBUG: available_functions: ", available_functions)

            messages.append({
                "role": "tool",
                "content": f"Called the {func['tool_name']} function.",
            })

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

                # Check to see if the function response is a string. If so, return it.
                if isinstance(function_response, str):

                    # Check to see if the function response is a response object.
                    if function_response == "Conversation Summarized.":
                        
                        # Stop code execution here.
                        return function_response
                
                # Test to see if the function response is a response object.
                if hasattr(function_response, 'get_data') and callable(function_response.get_data):
                    print("-- DEBUG: function_response: ", function_response.get_data(as_text=True))
                    func_response_text = function_response.get_data(as_text=True)
                else:
                    # Test to see if it's just a string. If not force it.
                    func_response_text = str(function_response)

                print("-- DEBUG: func_response_text: ", func_response_text)

                # Add the tool response to the conversation
                tool_messages = []

                init_sys_msg = get_initial_system_message()['content']

                tool_messages.append({
                    "tool_call_id": tool_call.id, 
                    "role": "tool", # Indicates this message is from tool use
                    "name": function_name,
                    "content": f"""{ init_sys_msg }\n\nCan you summarize the conversation for me using the function tool calls? Focus on the basic conversational details and relevant information, and make it sound conversational, like a memory? Please keep it short, yet relevant. Examples are: "Today, I ..." or "I asked about ...".\n\nIf the data that comes back is weather data, reply simply with the weather information. If asked for time, simply speak the time. If it's JSON format, make it sound human readable.
                    \n\n{ func_response_text }.""",
                })

                # Insert this as a message into the groq_messages table
                # But first, check to see if function_response as a get_data method.
                if hasattr(function_response, 'get_data') and callable(function_response.get_data):
                    content_out = function_response.get_data(as_text=True)
                else:
                    content_out = str(function_response)

                print_debug_line(f" -- The content_out is: { content_out }.", "white")

                if str(function_name).strip() != "summarize_conversation":
                    
                    sql("""INSERT INTO groq_messages (conv_id, msg_role, msg_content, msg_tool_name)
                    VALUES (0, 'tool', %s, %s);""", (content_out, function_name, ))

                    # Make a second API call with the updated conversation
                    second_response = client.chat.completions.create(
                        messages=tool_messages,
                        model="llama3-8b-8192",
                    )

                    print("-- DEBUG: second_response: ", second_response)

                    # Return the final response
                    return second_response.choices[0].message.content
        
        else:
            print("-- DEBUG: Not a tool call.")

        return response_message.content
    except Exception as e:
        return str(e)


# Route to summarize the conversation. It's called internally when user asks to summarize chat.
@app.route("/summarize_conversation", methods=["POST"])
def summarize_conversation():

    memories = get_tapestry_memories()

    conv_id = 0
    total_tokens = 0

    for mem in memories:
        total_tokens += get_token_count(mem['conv_summary'])

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
        total_tokens += get_token_count(message['msg_content'])

    print_debug_line(f" -- The total tokens in the conversation are: { total_tokens }.", "green")
    
    messages.append({
        "role": "user",
        "content": "Let's create a summary of the entire conversation up to this point. Write it as if it was a memory. Do not include previous memories in this summary, unless relevant and related.",
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


# Route to show the memories as a JSON object.
@app.route("/show_memories", methods=["POST"])
def show_memories():
    messages_data = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        ORDER BY msg_created, msg_id;""")

    output_template = render_template("history.html", messages=messages_data)

    return jsonify({
        "vbox": output_template
    })


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


#################### TEMPLATE FUNCTIONS START ####################


@app.template_filter('linebreaksbr')
def linebreaksbr(text):
    return text.replace("\n", "<br />")


@app.template_filter('readable_date')
def readable_date(date):

    ny_tz = pytz.timezone('America/New_York')
    utc_time = str(date)
    utc_dt = datetime.strptime(utc_time, '%Y-%m-%d %H:%M:%S')
    ny_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(ny_tz)

    # Return date in the format of ["Mon, Jan 1st '24", "12:00 am"]
    return ny_dt.strftime('%a, %b %d, \'%y, %I:%M %p').replace(' 0', ' ').replace('AM', 'am').replace('PM', 'pm')

@app.template_filter('readable_date_time')
def readable_date_time(date):
    # Return date in the format of ["Mon, Jan 1st '24"]
    return date.strftime('%a, %b %d, \'%y').replace(' 0', ' ')


#################### TEMPLATE FUNCTIONS END ####################


##########################  TEST FUNCTIONS  ##########################


def test():
    response = chat_completion([{
        "role": "user",
        "content": "Hello! I'm George.",
    }])
    print(jsonify({"reply": response}))


##########################  MAIN APPLICATION  ##########################


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