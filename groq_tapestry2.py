import datetime
from datetime import datetime, timedelta
from groq import Groq # type: ignore
from flask import jsonify

from groq_db_functs import *
from groq_system_functs import print_debug_line



# Steps for how were going to create this tapestry:

# 1. Set up `start_date`, `todays_date` and the iterative date `i_date`.
# 2. Initiate `i_date` as the `start_date`.
# 3. Start a loop while i_date
# 4. Have a function for checking conversational summaries.
# 5. Have a function for checking daily summaries.
# 6. Have a function for checking weekly summaries.
# 7. Have a function for checking monthly summaries.



# First we start with the main thread, which is a loop that starts from the first timestamp (msg_created) of the messages from the `messages` table.

### MAIN START ###

def main():

    # 1 Set up `start_date`, `todays_date` and the iterative date `i_date`.
    start_date = get_start_date()
    todays_date = get_todays_date()

    # 2. Initiate `i_date` as `start_date`.
    i_date = start_date

    # 3. Start the loop
    while i_date < todays_date:

        ### THIS IS WHERE WE PUT OUR MAIN ROUTINE CALLING FUNCTIONS FROM AROUND THE SYSTEM ###

        # Check every conversation with conv_id > 0. 0 is reserved for the current conversation.
        check_conversational_summaries(i_date)

        # Check every day summary before `i_date`, as we're not done with today.
        check_daily_summary(i_date)

        # Check every week summary before week of `i_date` as we're still in the week.
        check_weekly_summary(i_date)

        # Check for every month summary before month of `i_date`.
        check_monthly_summary(i_date)


        # At the end, we increment by one day
        i_date = (datetime.strptime(i_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

### MAIN END ###




# Check and create conversational summaries.

def check_conversational_summaries(i_date):

    # 1. Check for `messages` from `i_date`.
    # 2. Group `messages` by `conv_id`.
    sql_messages = sql("""SELECT conv_id FROM groq_messages GROUP BY conv_id HAVING DATE(MIN(msg_created)) = %s""", (i_date, ))

    # 3. If `messages``, check for `conversational_summary` by `conv_id`.
    for conv_id in sql_messages:
        new_conv_id = check_single_conversational_summary(conv_id)
        print_debug_line(f" -- The new conv_id is `new_conv_id`: {new_conv_id}.", "green")

    print_debug_line(f" -- The conversational summaries for `i_date`: {i_date} have been checked.", "green")


def check_single_conversational_summary(conv_id):
    # 1. Check for `conversational_summary` by `conv_id`.
    sql_conversational_summary = sql("""SELECT * FROM groq_conversations WHERE conv_id = %s AND conv_type_id = 0""", (conv_id, ))

    # 2. If no `conversational_summary`, `create_conversational_summary(conv_id)`.
    if not sql_conversational_summary:

        # 3. If no `conversational_summary`, `create_conversational_summary(conv_id)``.
        conv_id = create_conversational_summary(conv_id)

    return conv_id
    

def create_conversational_summary(conv_id):
    # TODO -> Loop through messages and combine them to create a summary for the whole conversation. Maybe by sentiment analysis or something else.

    # 1. Get `messages` for conv_id.
    sql_messages = sql("""SELECT * FROM groq_messages WHERE conv_id = %s ORDER BY msg_created, msg_id;""", (conv_id, ))

    # 2. Call the API to generate a conversational summary `call_api_for_level_summary(messages)`.
    messages = []
    for message in sql_messages:
        messages.append({
            "role": message['role'],
            "content": message['content']
        })
    
    conversational_summary = call_api_for_level_summary(messages)

    # 3. Save the `conversational_summary` to the database.
    new_conv_id = sql("""INSERT INTO groq_conversations (conv_id, conv_type_id, conv_summary) VALUES (%s, 0, %s)""", (conv_id, conversational_summary))
    print_debug_line(f" -- Conversation restored for `conv_id`: {new_conv_id}.", "green")
    
    return new_conv_id


# Check and create daily summaries.

def check_daily_summary(i_date):
    # 1. Check for `daily_summaries`
    sql_daily_summaries = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 1""", (i_date, ))

    # 2. If no `daily_summaries`, `create_daily_summary(i_date)`.
    if not sql_daily_summaries:
        conv_id = create_daily_summary(i_date)
    
    else:
        conv_id = sql_daily_summaries[0]['conv_id']

    return conv_id

def create_daily_summary(i_date):

    print_debug_line(f" -- `create_daily_summary` started for `i_date`: {i_date}.", "blue")

    # 1. Get `conversational_summaries` for `i_date` after we check its integrity.
    check_conversational_summaries(i_date)

    sql_conv_summaries = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 0""", (i_date, ))

    # Set up the list of conversational summaries for the day.
    conversational_summary_ids = []

    # 2. Now, loop through the `conversational_summaries` to check the conversational summaries.
    for conv_summary in sql_conv_summaries:
        conversational_summary_ids.append(conv_summary['conv_id'])
    
    # If we get here, it means that the conversational summaries have been created.

    # 3. Get `conversational_summaries` for `i_date`.
    messages = []
    messages.append({
        "role": "system",
        "content": load_tapestry()
    })
    messages.append({
        "role": "system",
        "content": prompt_for_daily_summary()
    })
    messages.append({
        "role": "system",
        "content": "-- The conversation starts here."
    })

    conversational_summaries = get_conversational_summaries_for_day(i_date)

    messages.append({
        "role": "system",
        "content": conversational_summaries
    })
    messages.append({
        "role": "system",
        "content": "-- The conversation ends here."
    })

    # 4. Call the API to generate a daily summary `call_api_for_level_summary(messages)`.
    daily_summary_response = call_api_for_level_summary(messages)

    # Now insert in database as a daily summary.
    conv_id = sql("""INSERT INTO groq_conversations (conv_type_id, conv_summary, conv_first_msg, conv_last_msg) VALUES (1, %s, %s, %s)""", (daily_summary_response, i_date, i_date))

    print_debug_line(f" -- Daily summary created for `i_date`: {i_date}.", "green")

    # Get conversational summaries for the day and update them with the new daily summary we're creating.
    for conv_id in conversational_summary_ids:
        sql("""UPDATE groq_conversations SET conv_parent_id = %s WHERE conv_id = %s""", (conv_id, conv_id))
    
    return conv_id


# Check and create weekly summaries.

def check_weekly_summary(i_date):
    # 1. Check for `weekly_summaries`
    sql_weekly_summaries = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 2""", (i_date, ))

    # 2. If no `weekly_summaries`, `create_weekly_summary(i_date)`.
    if not sql_weekly_summaries:
        create_weekly_summary(i_date)
        print_debug_line(f" -- Weekly summary created for `i_date`: {i_date}.", "green")
    else:
        print_debug_line(f" -- Weekly summary already exists for `i_date`: {i_date}.", "yellow")
    

def create_weekly_summary(i_date):
    
    print_debug_line(f" -- `create_weekly_summary` started for `i_date`: {i_date}.", "blue")

    # 1. Get `daily_summaries` for the week of `i_date`.
    monday_of_week = get_monday_of_week(i_date)
    sunday_of_week = get_sunday_of_week(i_date)
    i_week_day = monday_of_week

    # Set up the list of daily summaries for the week.
    daily_summary_ids = []

    # Now, loop through the week to check the daily summaries.
    while i_week_day <= sunday_of_week:

        # Let's get the day name from the date:
        day_name = datetime.strptime(i_week_day, "%Y-%m-%d").strftime("%A")

        print_debug_line(f" -- First, checking daily summary for `i_week_day` ({ day_name }): {i_week_day}.", "blue")

        # First, we check the daily summary itself to make sure it's whole.
        check_daily_summary(i_week_day)

        # Gathering the daily summaries based on `i_week_day` for the week to update them with the new weekly summary we're creating.
        sql_daily_summary = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 1""", (i_week_day, ))
        
        # If we find one today (i_week_day), we add it to the list.
        if sql_daily_summary:
            daily_summary_ids.append(sql_daily_summary[0]['conv_id'])
        
    
    # If we get here, it means that the daily summaries have been created.
    print_debug_line(f" -- Daily summaries created for the week of `i_date`: {i_date}.", "green")

    # Get `daily_summaries` for the week of `i_date` between `monday_of_week` and `sunday_of_week`.
    messages = []
    messages.append({
        "role": "system",
        "content": load_tapestry()
    })
    messages.append({
        "role": "system",
        "content": prompt_for_weekly_summary()
    })
    messages.append({
        "role": "system",
        "content": "-- The conversation starts here."
    })

    daily_summaries = get_daily_summaries_for_week(i_date)

    messages.append({
        "role": "system",
        "content": daily_summaries
    })
    messages.append({
        "role": "system",
        "content": "-- The conversation ends here."
    })

    # 2. Call the API to generate a weekly summary 
    weekly_summary_response = call_api_for_level_summary(messages)
    
    # Now insert in database as a weekly summary.
    conv_id = sql("""INSERT INTO groq_conversations (conv_type_id, conv_summary) VALUES (2, %s)""", (weekly_summary_response, ))

    print_debug_line(f" -- Weekly summary created for `i_date`: {i_date}.", "green")

    # Now update the daily summaries with the parent conv_id.
    for conv_id in daily_summary_ids:
        sql("""UPDATE groq_conversations SET conv_parent_id = %s WHERE conv_id = %s""", (conv_id, conv_id))
    
    return conv_id


# Check and create monthly summaries.

def check_monthly_summary(i_date):
    # 1. Check for `monthly_summaries`
    # 2. If no `monthly_summaries`, `create_monthly_summary(i_date)`.
    pass

def create_monthly_summary(i_date):
    # 1. Get `daily_summaries` for the month of `i_date`.
    # 2. Loop through the `daily_summaries` and `weekly_summaries` and check each one using `check_daily_summary(i_date)` and `check_weekly_summary(i_date)`.
    check_weekly_summary(i_date) # For each full week in the month.
    check_daily_summary(i_date) # For each day in the month, not in full week of month.
    # 3. Call the API to generate a monthly summary `call_api_for_level_summary(messages)`.
    pass




# Get summaries

def get_conversational_summaries_for_day(i_date):
    # Return the summaries in text format with date of day preceeding it.
    conversational_summaries_for_day = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 0""", (i_date, ))

    messages = []
    for summary in conversational_summaries_for_day:
        messages.append(str(summary['conv_first_msg']) + "\n" + summary['conv_summary'])

    return "\n\n".join(messages)

def get_daily_summaries_for_week(i_date):
    # Return the summaries in text format with date of day preceeding it.
    daily_summaries_for_week = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 1""", (i_date, ))

    summaries_list = []
    for summary in daily_summaries_for_week:
        summaries_list.append(str(summary['conv_first_msg']) + "\n" + summary['conv_summary'])

    return "\n\n".join(summaries_list)

def get_weekly_summaries_for_month(i_date):
    # Return the summaries in text format from the week preceeding it.
    
    # TODO -> Not simple. REDO.
    weekly_summaries_for_month = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 2""", (i_date, ))

    messages = []
    for summary in weekly_summaries_for_month:
        messages.append(str(summary['conv_first_msg']) + "\n" + summary['conv_summary'])

    return "\n\n".join(messages)

    



def load_tapestry(end_date = None):
    if not end_date:
        end_date = get_todays_date()
        end_date_and_time = get_todays_date_and_time()
    else:
        end_date = str(end_date)
        end_date_and_time = str(end_date) + " 23:59:59"

    print_debug_line(f" -- The end date is `end_date`: {end_date}.", "green")
    print_debug_line(f" -- The end date and time is `end_date_and_time`: {end_date_and_time}.", "green")

    # We check for monthly summaries before the first of the month of `end_date`.
    #   Then, we add them to `tapestry`
    # We check for weekly summaries before the monday of the week of `end_date`.
    #   Then, we add them to `tapestry`
    # We check for daily summaries before `end_date`.
    #   Then, we add them to `tapestry`
    # We check for conversational summaries before `end_date`.
    #   Then, we add them to `tapestry`

def prompt_for_weekly_summary():
    return "From the following conversation, createa a weekly summary that follows the following guidelines..."



def call_api_for_level_summary(messages):
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

    return response.content


### Useful internal functions. ###

def get_start_date():
    start_date = sql("""SELECT DATE(MIN(msg_created)) AS start_date FROM messages""")
    if start_date:
        return str(start_date[0]['start_date'].strftime("%Y-%m-%d"))

def get_todays_date():
    return str(datetime.now().strftime("%Y-%m-%d"))

def get_todays_date_and_time():
    return str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def get_monday_of_week(date):
    date = datetime.strptime(str(date), "%Y-%m-%d")
    monday = date - timedelta(days=date.weekday())
    return monday.strftime("%Y-%m-%d")

def get_sunday_of_week(date):
    date = datetime.strptime(str(date), "%Y-%m-%d")
    sunday = date + timedelta(days=(6 - date.weekday()))
    return sunday.strftime("%Y-%m-%d")

