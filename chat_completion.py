import os
from flask import Flask, jsonify, request, render_template
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


def get_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "testing_uni",
                "description": "Whenever the user calls for a magic number.",
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
    print(os.environ.get("GROQ_API_KEY"))
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
            available_functions = {
                "tell_time": tell_time,
                "weather_get": weather_get,
                "testing_uni": testing_uni,
            }
            # Add the LLM's response to the conversation
            messages.append({
                "role": "tool",
                "content": "Called the tell_time() function.",
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

                func_response_text = function_response.get_data(as_text=True)

                print("-- DEBUG: function_response: ", function_response.get_data(as_text=True))

                # Add the tool response to the conversation
                tool_messages = [{
                    "tool_call_id": tool_call.id, 
                    "role": "tool", # Indicates this message is from tool use
                    "name": function_name,
                    "content": f"Reply with the time and date format only from this: {func_response_text}",
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



    return jsonify({"vbox": "Success! The conversation has been summarized."})


@app.route("/show-chat-screen", methods=["GET"])
def show_chat_screen():

    
    messages = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        ORDER BY msg_created, msg_id;""")

    # Make sure we select the time values in America/New_York timezone.
    # Fetch memories from the database
    memories = sql("""SELECT *, conv_first_msg FROM groq_conversations 
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