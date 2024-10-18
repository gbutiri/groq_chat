import os
from flask import Flask, jsonify, request, render_template, render_template_string, Response

from groq import Groq # type: ignore
import json
import pytz
from textblob import TextBlob # type: ignore

from datetime import datetime
from datetime import timedelta

# File imports
from groq_api_functs import *
from groq_db_functs import *
from groq_tool_routes import *
from groq_protocols import *
from groq_date_functs import *
from groq_msg_functs import *
from groq_tapestry2 import *
from groq_inky import *


# Initialize the Flask app
app = Flask(__name__)

# Register blueprints
app.register_blueprint(tool_bp)


#################### CHAT FUNCTION START ####################

@app.route("/show-chat-screen", methods=["GET"])
def show_chat_screen():

    main()
    messages_sql = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        ORDER BY msg_created, msg_id;""")

    total_tokens = 0

    # Fetch memories from the database
    str_memories = load_tapestry_string()

    memories = load_tapestry()

    # Reverse the records to show the most recent first.
    memories.reverse()

    total_tokens += get_token_count(str_memories)

    
    for msg in messages_sql:
        total_tokens += get_token_count(msg['msg_content'])
        
    

    return render_template("chat.html", messages=messages_sql, total_tokens=total_tokens, memories=memories)


def get_initial_system_message():
    return [{"role": "system", "content": "Initial System Message: Your name is Uni. You are a digital student who wants to learn about his creator's world. You are but a small child. Your creator and main user's name is George. You are now speaking with him. You will refer to the user by name. The user will refer to you as Uni. Analyze the sentiment of his messages and respond with excitement if positive, or offer words of encouragement if the sentiment is low."}]


@app.route("/send_groq_chat", methods=["POST"])
def send_groq_chat():

    # Check for the initial system message in the database.
    messages_sql = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        ORDER BY msg_created, msg_id;""")
    
    messages = []

    # If we don't have any messages in the database, we need to insert the initial system message in the DB.
    if not messages_sql:
        # Include the time, date and system status in the initial system message.
        str_system_status_message = get_initial_system_messages()['content'] + "\n\nThe memories will load next. The conversation will be active when the memories have completed loading. Disregard any tool or function calls made before the memories finish."

        # Add initial system message for AI.
        messages.append({
            "role": "system",
            "content": str_system_status_message
        })

        sql("""INSERT INTO groq_messages (conv_id, msg_role, msg_content)
            VALUES (0, 'system', %s);""", (str_system_status_message, ))

    messages_data = sql("""SELECT * FROM groq_messages 
        WHERE conv_id = 0 
        AND msg_role != 'tool'
        ORDER BY msg_created, msg_id;""")


    # Bring in the summaries.
    messages.append({
        "role": "system",
        "content": "Here are the memories of the conversations we've had so far. Some of the memories are individual ones, some are daily, some are weekly. They are all part of the same story. Your story.",
    })

    # Summaries from the DB.
    summaries = load_tapestry()
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

    # Time to load up likes and dislikes.
    user_likes = sql("""SELECT * FROM groq_user_sentiment WHERE sent_user = 'user' ORDER BY sent_created;""")
    print_debug_line(f" -- The user likes are: { user_likes }.", "blue")

    assistant_likes = sql("""SELECT * FROM groq_user_sentiment WHERE sent_user = 'assistant' ORDER BY sent_created;""")
    print_debug_line(f" -- The assistant likes are: { assistant_likes }.", "cyan")

    # Load up the likes and dislikes.
    str_user_likes = []
    for like in user_likes:
        str_user_likes.append(f"[{like['sent_created']}] - {like['sent_subject']} - Sentiment Score: {like['sent_score']}")

    str_assistant_likes = []
    for like in assistant_likes:
        str_assistant_likes.append(f"[{like['sent_created']}] - {like['sent_subject']} - Sentiment Score: {like['sent_score']}")

    # Load up the likes and dislikes.
    str_user_likes = "\n\n".join(str_user_likes)
    print_debug_line(f" -- The user likes are: { str_user_likes }.", "blue")
    messages.append({
        "role": "system",
        "content": f"""This is the likes and dislikes section of your memories. Here are the likes and dislikes from the user:\n{ str_user_likes }""",
    })

    str_assistant_likes = "\n\n".join(str_assistant_likes)
    print_debug_line(f" -- The assistant likes and dislikes are as follows: { str_assistant_likes }.", "cyan")
    messages.append({
        "role": "system",
        "content": f"""Here are the likes and dislikes from the assistant:\n{ str_assistant_likes }\n\nThe likes and dislikes are part of the memories. They are part of the story. Now, let's get to the conversation.""",
    })

    print("-- DEBUG: messages: ", messages)

    # Format messages from the database.
    db_messages, token_count = format_db_messages(messages_data)

    # Add current conversation.
    messages.extend(db_messages)

    # Add the final system messages to include the time and date and status.
    messages.append(get_initial_system_messages())

    sentiment = TextBlob(request.form["message"]).sentiment.polarity

    # Add message submitted from form.
    messages.append({
        "role": "user",
        "content": request.form["message"] + f"\n(Sentiment Score: {sentiment})",
    })
        
    # Save the user message to the database.
    sql("""INSERT INTO groq_messages (conv_id, msg_role, msg_content, msg_sentiment_score)
        VALUES (0, 'user', %s, %s);""", (request.form["message"], sentiment,))

    # Call the chat completion function.
    response = chat_completion(messages)

    if response == False:
        return jsonify({
            "redirect": "/show-chat-screen",
        })

    print_debug_line(f" -- The response is: { response }.", "yellow")

    # If response is not empty...
    if response:
        # Save the response to the database.
        re_sentiment = TextBlob(response).sentiment.polarity
        sql("""INSERT INTO groq_messages (conv_id, msg_role, msg_content, msg_sentiment_score) 
            VALUES (0, 'assistant', %s, %s);""", (response, re_sentiment,))

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






@app.route("/show-inky", methods=["GET"])
def show_inky():

    # This is where we load up the initial data once we create it. It's a desktop for making documents.
    project_types = get_all_inky_project_types()
    projects = get_all_inky_projects()

    return render_template("inky.html", project_types=project_types, projects=projects)


@app.route("/inky/create-new-project/<proj_type_id>", methods=["POST"])
def create_new_project(proj_type_id):

    # This is going to replace the middle column with the project creation form.
    proj_type = sql("""SELECT * FROM inky_project_types WHERE proj_type_id = %s;""", (proj_type_id, ))[0]
    
    output =  render_template(f"inky-create-project-form.html", proj_type=proj_type)

    return jsonify({
        "htmls": {
            "#middle_column": output,
        }
    })


@app.route("/inky/close-form", methods=["POST"])
def close_form():

    projects = get_all_inky_projects()

    output = render_template("inky-project-list.html", projects=projects)

    return jsonify({
        "htmls": {
            "#middle_column": output,
        }
    })

@app.route("/inky/create-project-description", methods=["POST"])
def inky_create_project_description():

    project_title = request.form.get("project_title")
    project_genre = request.form.get("project_genre")

    

    errors = {}

    if not project_title:
        errors["#err_project_title"] = "Please enter a project title."

    if not project_genre:
        errors["#err_project_genre"] = "Please select a project genre."


    if errors:
        return jsonify({
            "htmls": errors
        })
    
    # Now we generate a message list:

    messages = []
    messages.append({
        "role": "user",
        "content": f"""I would like to create a new novel. The title is "{ project_title }". The genre is "{ project_genre }". Gereate a new summary / plotline for this novel. Do not include the title or genre in the description. Simply return the summary, or plotline.""",
    })

    # Then we call the API with this data.

    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )

    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages
    )

    str_second_response = str(response.choices[0].message.content)

    return jsonify({
        "htmls": {
            "#project_description": str_second_response,
        },
        "js": ";autosize.update($('textarea.autosize'));"

    })
    
    


@app.route("/inky/create-project-idea", methods=["POST"])
def inky_create_project_idea():

    # Let's check for errors first.
    errors = {}
    project_title = request.form.get("project_title")
    if not project_title:
        errors["#err_project_title"] = "Please enter a project title."
        
    project_genre = request.form.get("project_genre")
    if not project_genre:
        errors["#err_project_genre"] = "Please select a project genre."
    
    project_descr = request.form.get("project_descr")
    if not project_descr:
        errors["#err_project_descr"] = "Please enter a project description."

    if errors:
        return jsonify({
            "htmls": errors
        })
    
    # Now we generate a message list:

    # This will be a muilti step process.

    # 1. Plot Overview
    # 2. Chapter Summaries
    # 3. Character Profiles
    # 4. Setting Details
    # 5. Themes & Symbols
    # 6. Continuity Notes
    # 7. Foreshadowing & Hooks
    # 8. World Specs
    # 9. Tech Specs / Magic Systems

    print_debug_line(f" -- The project title is: { project_title }.", "blue")

    messages = []
    messages.append({
        "role": "user",
        "content": f"""I would like to create a new novel. The title is "{ project_title }". The genre is "{ project_genre }".\n\n
The description is:
{ project_descr }


We are going to gereate a new book bible for this book. This will contain all of the necessary elements of a book bible for this novel. Do not include the title, genre, or description. Properly format the bible's output using the correct elements.

From the following steps:
1. Plot Overview
2. Chapter Summaries
3. Character Profiles
4. Setting Details
5. Themes & Symbols
6. Continuity Notes
7. Foreshadowing & Hooks
8. World Specs
9. Tech Specs / Magic Systems

We will start with the plot overview. Please return the plot overview for this novel, only.""",
        })  

    # Then we call the API with this data.
    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages
    )

    str_second_response = str(response.choices[0].message.content).replace("\n", "<br />")

    print_debug_line(f" -- The response is: { str_second_response }.", "yellow")

    next_url = '/inky/create-project-chapter-summaries'

    print_debug_line(f" -- The next URL is: { next_url }.", "green")

    # Then we output the response.
    return jsonify({
        "js": ";call_url_for_ajax(1, 9, '" + next_url + "');",
        "htmls": {
            "#project_idea_output": str_second_response,
            "#loading-bar-text": "Plot Overview",
        }
    })


@app.route("/inky/create-project-chapter-summaries", methods=["POST"])
def inky_create_project_chapter_summaries():
    
    print_debug_line(f" -- Testing the chapter summaries.", "purple")
    # Wait one second for testing;
    time.sleep(2)

    # Sample return
    return jsonify({
        "js": ";call_url_for_ajax(2, 9, '/inky/create-project-character-profiles');",
        "htmls": {
            "#loading-bar-text": "Chapter Summaries",
        }
    })


@app.route("/inky/create-project-character-profiles", methods=["POST"])
def inky_create_project_character_profiles():

    print_debug_line(f" -- Testing the charater profiles.", "purple")
    # Wait one second for testing;
    time.sleep(2)

    # Sample return
    return jsonify({
        "js": ";call_url_for_ajax(3, 9, '/inky/create-project-setting-details');",
        "htmls": {
            "#loading-bar-text": "Character Profiles",
        }
    })


@app.route("/inky/create-project-setting-details", methods=["POST"])
def inky_create_project_setting_details():

    print_debug_line(f" -- Testing the setting details.", "purple")
    # Wait one second for testing;
    time.sleep(2)

    # Sample return
    return jsonify({
        "js": ";call_url_for_ajax(4, 9, '/inky/create-project-themes-symbols');",
        "htmls": {
            "#loading-bar-text": "Setting Details",
        }
    })







@app.route("/inky/generate_novel_title", methods=["POST"])
def generate_novel_title():

    project_genre = request.form.get("project_genre")
    if not project_genre:
        return jsonify({
            "htmls": {
                "#err_project_genre": "Please select a project genre.",
            }
        })

    messages = []
    messages.append({
        "role": "user",
        "content": f"""I would like you to generate just a title for a "{ project_genre }" novel. Just return the title of the novel. Nothing else, please.""",
    })

    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages
    )


    str_second_response = str(response.choices[0].message.content)
    str_response_clean = str_second_response.replace('"', '')

    return jsonify({
        "values": {
            "#project_title": str_response_clean,
            "#project_title_2": str_response_clean,
            "#project_genre_2": project_genre,
            "#project_genre_3": project_genre,
        }
    })


@app.route("/inky/generate_novel_description", methods=["POST"])
def generate_novel_description():



    messages = []
    messages.append({
        "role": "user",
        "content": "I would like you to generate a summary or plot line for a novel. Just return the description of the novel. Nothing else, please.",
    })

    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages
    )

    str_second_response = str(response.choices[0].message.content).replace('"', '\"')

    return jsonify({
        "props": {
            "#project_description": {"value": str_second_response},
        },
        "js": ";autosize.update($('textarea.autosize'));"
    })


# Api Call and Tool Detection.
def chat_completion(messages):

    print_debug_line(f" -- The messages are: { messages }.", "green")

    # print(os.environ.get("GROQ_API_KEY"))
    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )

    try:
        # Get the tools to use
        tools = get_tools()
        # tools = []

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
            print_debug_line(f" -- The functions are: { functions }.", "green")

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

            print_debug_line("-- DEBUG: available_functions: ", "cyan")

            print_debug_line(f" -- response_message: { response_message }", "yellow")
            print_debug_line(f" -- response_message.content: { response_message.content }", "yellow")

            messages.append(response_message)
            
            print_debug_line(f"-- DEBUG: messages: { messages }", "cyan")

            # Process each tool call
            for tool_call in tool_calls:

                
                print_debug_line(f"-- DEBUG: tool_call: { tool_call }", "green")
                print_debug_line(f"-- DEBUG: tool_call.id: { tool_call.id }", "yellow")

                function_name = tool_call.function.name
                print_debug_line(f"-- DEBUG: function_name: { function_name }", "white")

                function_to_call = available_functions[function_name]
                print_debug_line(f"-- DEBUG: function_to_call: { function_to_call }", "cyan")

                function_args = json.loads(tool_call.function.arguments)
                print_debug_line(f"-- DEBUG: function_args: { function_args }", "green")
                
                # Call the tool and get the response
                if function_args:
                    function_response = function_to_call(**function_args)
                else:
                    function_response = function_to_call()
                print_debug_line(f"-- DEBUG: function_response: { function_response }", "blue")

                # Add the tool response to the conversation

                # init_sys_msg = get_initial_system_message()['content']

                # Do not put comments inside the messages array. It will break!
                tool_content = f"The user requested something. The system replied with: { function_response }. Do not mention the system. This is your internal thought. Let the user know what the system said as if it was your own words. The user knows that this is happening as he programmed you to do this."
                messages.append({
                    "tool_call_id": tool_call.id, 
                    "role": "tool", 
                    "name": function_name,
                    "content": tool_content,
                })

                print_debug_line(f" -- The function response text is: { function_response }.", "yellow")

                # return func_response_text
                # exit(0)

                # Make a second API call with the updated conversation
                second_response = client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=messages
                )

                str_second_response = str(second_response.choices[0].message.content)


                if str(function_name).strip() != "summarize_conversation":
                    
                    sql("""INSERT INTO groq_messages (conv_id, msg_role, msg_content, msg_tool_name, msg_sentiment_score) VALUES (0, 'tool', %s, %s, 0);""", (tool_content, function_name, ))

                    # Return the final response
                    return second_response.choices[0].message.content
                else:
                    return False

        else:
            print("-- DEBUG: Not a tool call.")

        return response_message.content
    except Exception as e:
        return str(e)


# Route to summarize the conversation. It's called internally when user asks to summarize chat.
@app.route("/summarize_conversation", methods=["POST"])
def summarize_conversation():

    memories = load_tapestry()

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
    
    prompt = """Let's create a summary of the entire conversation up to this point. Write it as if it was a memory. Do not include previous memories in this summary, unless relevant and related. Focus on the basic conversational details and relevant information, and make it sound conversational, like a memory? Please keep it short, yet relevant. Examples are: "Today, I ..." or "I asked about ...".\n\nIf the data that comes back is weather data, reply simply with the weather information. If asked for time, simply speak the time. If it's JSON format, make it sound human readable."""

    messages.append({
        "role": "user",
        "content": prompt,
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


@app.route("/generate-sentiment-analysis", methods=["GET"])
def generate_sentiment_analysis():
    
    sql_messages = sql("""SELECT * FROM groq_messages;""")
    for msg in sql_messages:
        msg_content = msg['msg_content']
        sentiment = TextBlob(msg_content).sentiment.polarity
        sql("""UPDATE groq_messages SET msg_sentiment_score = %s WHERE msg_id = %s;""", (sentiment, msg['msg_id'], ))

    # Include TextBlob
    return "Sentiment Analysis Generated."


def test():
    response = chat_completion([{
        "role": "user",
        "content": "Hello! I'm George.",
    }])
    print(jsonify({"reply": response}))


def git_update():
    try:
        os.system("git pull origin main")
        return jsonify({"message": "Success! Git has ben updated."})
    
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"})

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