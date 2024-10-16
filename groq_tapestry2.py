import os
import datetime
import time

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from groq import Groq # type: ignore
from flask import Flask, jsonify, request, render_template, render_template_string


from groq_db_functs import *
from groq_system_functs import print_debug_line
from groq_date_functs import *

# Initialize the Flask app
app = Flask(__name__)


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

@app.route("/restore-tapestry", methods=["GET"])
def main():

    tapestry = load_tapestry()
    # return jsonify({"tapestry": tapestry})

    print_debug_line(" -- The main function has started.", "blue")

    # 1 Set up `start_date`, `todays_date` and the iterative date `i_date`.
    start_date = get_start_date()
    todays_date = get_todays_date()

    # 2. Initiate `i_date` as `start_date`.
    i_date = start_date

    # 3. Start the loop
    while i_date <= todays_date:

        ### THIS IS WHERE WE PUT OUR MAIN ROUTINE CALLING FUNCTIONS FROM AROUND THE SYSTEM ###

        # Check every conversation with conv_id > 0. 0 is reserved for the current conversation.
        check_conversational_summaries(i_date)

        # Check every day summary before `i_date`, as we're not done with today.
        check_daily_summary(i_date)

        # Check every week summary before week of `i_date` as we're still in the week.
        check_weekly_summary(i_date)

        # Check for every month summary before month of `i_date`.
        # check_monthly_summary(i_date)


        # At the end, we increment by one day
        i_date = (datetime.strptime(i_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    # Testing. So, we're stopping the execution.
    return jsonify({"vbox": "First test completed."})

### MAIN END ###



# Check and create conversational summaries.

def check_conversational_summaries(i_date):

    print_debug_line(f" -- `check_conversational_summaries` started for `i_date`: {i_date}. Getting conversation IDs for the day.", "blue")

    # 1. Check for `messages` from `i_date`.
    # 2. Group `messages` by `conv_id`.
    sql_messages = sql("""SELECT conv_id FROM groq_messages WHERE conv_id != 0 GROUP BY conv_id HAVING DATE(MIN(msg_created)) = %s""", (i_date, ))

    new_conv_id = False

    # 3. If `messages``, check for `conversational_summary` by `conv_id`.
    for message in sql_messages:
        conv_id = message['conv_id']
        new_conv_id = check_single_conversational_summary(conv_id)
        print_debug_line(f" -- The new conv_id is `new_conv_id`: {new_conv_id}.", "green")

    print_debug_line(f" -- The conversational summaries for `i_date`: {i_date} have been checked.", "green")

    return new_conv_id


def check_single_conversational_summary(conv_id):

    print_debug_line(f" -- `check_single_conversational_summary` started for `conv_id`: {conv_id}.", "blue")

    print_debug_line(f" -- Checking for existing `conversational_summary` by `conv_id`: {conv_id}.", "blue")

    # 1. Check for `conversational_summary` by `conv_id`.
    sql_conversational_summary = sql("""SELECT * FROM groq_conversations WHERE conv_id = %s AND conv_type_id = 0""", (conv_id, ))

    # 2. If no `conversational_summary`, `create_conversational_summary(conv_id)`.
    if not sql_conversational_summary:

        # 3. If no `conversational_summary`, `create_conversational_summary(conv_id)``.
        print_debug_line(f" -- No conversational summary found for `conv_id`: {conv_id}. Creating one now.", "yellow")
        conv_id = create_conversational_summary(conv_id)

    else:
        print_debug_line(f" -- Conversational summary already exists for `conv_id`: {conv_id}.", "yellow")
    
    print_debug_line(f" -- The conversational summary for `conv_id`: {conv_id} has been checked.", "green")

    return conv_id


def create_conversational_summary(conv_id):

    print_debug_line(f" -- `create_conversational_summary` started for `conv_id`: {conv_id}. Gathering messages...", "blue")

    # 1. Get `messages` for conv_id.
    sql_messages = sql("""SELECT * FROM groq_messages WHERE conv_id = %s ORDER BY msg_created, msg_id;""", (conv_id, ))

    # 2. Call the API to generate a conversational summary `call_api_for_level_summary(messages)`.
    messages = []

    messages.append({
        "role": "system",
        "content": load_tapestry_string()
    })
    messages.append({
        "role": "system",
        "content": prompt_for_conversational_summary()
    })
    messages.append({
        "role": "system",
        "content": "-- The conversation starts here."
    })

    # Generate the conversation content.
    lst_conversation_content = []
    for message in sql_messages:
        lst_conversation_content.append(f"{ message['msg_created'] }\n{ message['msg_role'] }: { message['msg_content'] }")
    
    messages.append({
        "role": "system",
        "content": "\n\n".join(lst_conversation_content)
    })

    messages.append({
        "role": "system",
        "content": "-- The conversation ends here."
    })
    
    # Calling the API to generate the conversational summary.
    print_debug_line(f" -- Calling the API for the conversational summary.", "blue")
    conversational_summary = call_api_for_level_summary(messages)

    # 3. Save the `conversational_summary` to the database.
    new_conv_id = sql("""INSERT INTO groq_conversations (conv_id, conv_type_id, conv_summary, conv_first_msg, conv_last_msg) VALUES (%s, 0, %s, %s, %s)""", (conv_id, conversational_summary, sql_messages[0]['msg_created'], sql_messages[-1]['msg_created'], ))
    print_debug_line(f" -- Conversation restored for `conv_id`: {new_conv_id}.", "green")
    
    return new_conv_id



# Check and create daily summaries.

def check_daily_summary(i_date):
    
    # 1. Check for `daily_summaries`
    
    print_debug_line(f" -- `check_daily_summary` started for `i_date`: {i_date}.", "blue")
    
    sql_daily_summaries = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 1""", (i_date, ))

    todays_date = get_todays_date()

    # 2. If no `daily_summaries`, `create_daily_summary(i_date)`.
    if not sql_daily_summaries and i_date < todays_date:
        print_debug_line(f" -- No daily summary found for `i_date`: {i_date}. Attempting to create one now.", "yellow")
        create_daily_summary(i_date)

    print_debug_line(f" -- Daily summary already exists for `i_date`: {i_date}.", "green")

def create_daily_summary(i_date):

    print_debug_line(f" -- `create_daily_summary` started for `i_date`: {i_date}.", "blue")

    # 1. Get `conversational_summaries` for `i_date` after we check its integrity.
    if check_conversational_summaries(i_date):

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
            "content": load_tapestry_string()
        })
        messages.append({
            "role": "system",
            "content": prompt_for_daily_summary()
        })
        messages.append({
            "role": "system",
            "content": "-- The conversation starts here."
        })

        str_conversational_summaries = get_conversational_summaries_for_day(i_date)
        print_debug_line(f" -- The conversational summaries for the day are `conversational_summaries`: {str_conversational_summaries}.", "white")

        messages.append({
            "role": "system",
            "content": str_conversational_summaries
        })
        messages.append({
            "role": "system",
            "content": "-- The conversation ends here."
        })

        # 4. Call the API to generate a daily summary `call_api_for_level_summary(messages)`.
        print_debug_line(f" -- Calling the API for the daily summary. Messages:\n\n{ messages }", "blue")
        daily_summary_response = call_api_for_level_summary(messages)

        print_debug_line(f" -- The daily summary response is `daily_summary_response`: {daily_summary_response}.", "white")

        # Now insert in database as a daily summary.
        conv_id = sql("""INSERT INTO groq_conversations (conv_type_id, conv_summary, conv_first_msg, conv_last_msg) VALUES (1, %s, %s, %s)""", (daily_summary_response, i_date, i_date))

        print_debug_line(f" -- Daily summary created for `i_date`: {i_date}.", "green")

        # Get conversational summaries for the day and update them with the new daily summary we're creating.
        for conv_id in conversational_summary_ids:
            sql("""UPDATE groq_conversations SET parent_id = %s WHERE conv_id = %s""", (conv_id, conv_id))
        
        return conv_id

    else:
        return False

# Check and create weekly summaries.

def check_weekly_summary(i_date):

    print_debug_line(f" -- `check_weekly_summary` started for `i_date`: {i_date}.", "blue")

    # 1. Check for `weekly_summaries`
    print_debug_line(f" -- Checking for existing `weekly_summaries` for `i_date`: {i_date}.", "blue")
    sql_weekly_summaries = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 2""", (i_date, ))

    # 2. If no `weekly_summaries`, `create_weekly_summary(i_date)`.
    if not sql_weekly_summaries:
        start_of_week = get_monday_of_week(i_date)
        create_weekly_summary(start_of_week)
        print_debug_line(f" -- Weekly summary created for `i_date`: {i_date}.", "green")
    else:
        print_debug_line(f" -- Weekly summary already exists for `i_date`: {i_date}.", "yellow")
    

def create_weekly_summary(i_date):
    
    print_debug_line(f" -- `create_weekly_summary` started for `i_date`: {i_date}.", "blue")

    monday_of_week = get_monday_of_week(i_date)
    
    # 1. Check for `daily_summaries` for the week of `i_date`.
    sql_existing_weekly = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 2""", (monday_of_week, ))

    if not sql_existing_weekly and i_date < monday_of_week:

        print_debug_line(f" -- Setting Monday, Sunday, and the weekly day iterator.", "blue")

        # 1. Get `daily_summaries` for the week of `i_date`.
        
        sunday_of_week = get_sunday_of_week(i_date)
        i_week_day = monday_of_week

        # Set up the list of daily summaries for the week.
        daily_summary_ids = []

        # Now, loop through the week to check the daily summaries.
        print_debug_line(f" -- Looping through the week of `i_date`: {i_date}.", "blue")
        while i_week_day <= sunday_of_week:

            # Let's get the day name from the date:
            day_name = datetime.strptime(i_week_day, "%Y-%m-%d").strftime("%A")
            print_debug_line(f" -- First, checking daily summary for `i_week_day` ({ day_name }): {i_week_day}.", "blue")

            # First, we check the daily summary itself to make sure it's whole.
            print_debug_line(f" -- Checking daily summary for `i_week_day` ({ day_name }): {i_week_day}.", "blue")
            check_daily_summary(i_week_day)

            # Gathering the daily summary based on `i_week_day` for the week to update them with the new weekly summary we're creating.
            sql_daily_summary = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 1""", (i_week_day, ))
            
            # If we find one today (i_week_day), we add it to the list.
            if sql_daily_summary:
                print_debug_line(f" -- Appending found daily summary for `i_week_day` ({ day_name }): {i_week_day}.", "blue")
                daily_summary_ids.append(sql_daily_summary[0]['conv_id'])
            
            # Increment the day by one.
            i_week_day = (datetime.strptime(i_week_day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # If we get here, it means that the daily summaries have been created.
        print_debug_line(f" -- Daily summaries created for the week of `i_date`: {i_date}.", "green")

        # Get `daily_summaries` for the week of `i_date` between `monday_of_week` and `sunday_of_week`.
        print_debug_line(f" -- Setting messages for the week of `i_date`: {i_date}.", "blue")
        messages = []
        messages.append({
            "role": "system",
            "content": load_tapestry_string()
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
        print_debug_line(f" -- Calling the API for the weekly summary.", "blue")
        weekly_summary_response = call_api_for_level_summary(messages)

            
        sunday_of_week_eod = (datetime.strptime(sunday_of_week, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")

        # Now insert in database as a weekly summary.
        conv_id = sql("""INSERT INTO groq_conversations (conv_type_id, conv_summary, conv_first_msg, conv_last_msg) VALUES (2, %s, %s, %s)""", (weekly_summary_response, monday_of_week, sunday_of_week_eod, ))

        print_debug_line(f" -- Weekly summary created for `i_date`: {i_date}.", "green")

        # Now update the daily summaries with the parent conv_id.
        for daily_summary_id in daily_summary_ids:
            sql("""UPDATE groq_conversations SET parent_id = %s WHERE conv_id = %s""", (conv_id, daily_summary_id, ))
        
        return conv_id

    else:
        return False

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

    monday_of_week = get_monday_of_week(i_date)
    sunday_of_week = get_sunday_of_week(i_date)

    print_debug_line(f" -- `get_daily_summaries_for_week` started for `i_date`: {i_date}.", "blue")

    # Return the summaries in text format with date of day preceeding it.
    daily_summaries_for_week = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) > %s AND DATE(conv_last_msg) < %s AND conv_type_id = 1""", (monday_of_week, sunday_of_week))
    print_debug_line(f" -- Getting daily summaries as a list now.", "green")

    summaries_list = []
    for summary in daily_summaries_for_week:
        print_debug_line(f" -- Getting daily summary for `summary['conv_first_msg']`: {summary['conv_first_msg']}.", "green")
        summaries_list.append(str(summary['conv_first_msg']) + "\n" + summary['conv_summary'])

    str_summaries = "\n\n".join(summaries_list)
    print_debug_line(f" -- The daily summaries for the week of `i_date`: {i_date} are `str_summaries`: {str_summaries}.", "green")

    return str_summaries

def get_weekly_summaries_for_month(i_date):
    # Return the summaries in text format from the week preceeding it.
    
    # TODO -> Not simple. REDO.
    weekly_summaries_for_month = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 2""", (i_date, ))

    messages = []
    for summary in weekly_summaries_for_month:
        messages.append(str(summary['conv_first_msg']) + "\n" + summary['conv_summary'])

    return "\n\n".join(messages)

    


@app.route("/get-tapestry", methods=["GET"])
@app.route("/get-tapestry/<end_date>", methods=["GET"])
def get_tapestry(end_date = None):

    if end_date is None:
        end_date = get_todays_date()

    tapestry = load_tapestry(end_date)

    return jsonify({"tapestry": tapestry})


def load_tapestry_string(end_date = None):
    tapestry = load_tapestry(end_date)
    print_debug_line(f" -- The tapestry is `tapestry`: {tapestry}.", "green")

    tapestry_output = ""
    for tapestry_item in tapestry:
        tapestry_output += tapestry_item['content'] + "\n\n"
    return tapestry_output

def load_tapestry(end_date = None):

    print("\n\n")

    # Short explanation.
    # We're going to pull memories from the database starting with the largest possible ones from the past, and smallest left overs from current month, week or day.

    # First date from the database from `groq_messages`.
    start_date = get_start_date()

    # Set up the tapestry output.
    lst_tapestry_ouput = []

    if not end_date:
        end_date = get_todays_date()
    else:
        end_date = str(end_date)

    print_debug_line(f" -- The `start_date` and `end_date` are : {start_date} and { end_date }.", "blue")


    i_date = start_date

    while i_date <= end_date:
        print_debug_line(f" -- Starting the loop iteration for `i_date`: {i_date}.", "blue")
        
        # Check for monthly summaries for the first of previous month.
        first_of_month = get_first_of_month(i_date)
        first_of_previous_month = (datetime.strptime(first_of_month, "%Y-%m-%d") - relativedelta(months=1)).strftime("%Y-%m-%d")
        print_debug_line(f" -- The first of the month is `first_of_month`: {first_of_month}.", "cyan")
        print_debug_line(f" -- The first of the previous month is `first_of_previous_month`: {first_of_previous_month}.", "cyan")

        # Check for montly summaries for this date.
        existing_monthly_summary = sql("SELECT * FROM groq_conversations LEFT JOIN groq_conv_types USING(conv_type_id) WHERE conv_type_id = 3 AND DATE(conv_first_msg) = %s;", (first_of_month, ))
        month_date_of_end_date = get_first_of_month(end_date)

        # if we have a monthly summary and we're not in the month of the end_date, we add it to the tapestry.

        if len(existing_monthly_summary) > 0 and first_of_month < month_date_of_end_date:
            print_debug_line(f" -- There is a monthly summary for the month of {first_of_previous_month}.", "cyan")
            str_monthly_summary = existing_monthly_summary[0]['conv_summary']
            lst_tapestry_ouput.append({
                "content": f"[{first_of_month}] - Monthly memory:\n{str_monthly_summary}",
                "conv_id": existing_monthly_summary[0]['conv_id'],
                "conv_summary": existing_monthly_summary[0]['conv_summary'],
                "conv_type_name": existing_monthly_summary[0]['conv_type_name'],
                "conv_first_msg": existing_monthly_summary[0]['conv_first_msg'],
                "conv_last_msg": existing_monthly_summary[0]['conv_last_msg'],
                "conv_type_color": existing_monthly_summary[0]['conv_type_color'],

            })

            # Incrememnt by one month.
            i_date = (datetime.strptime(first_of_month, "%Y-%m-%d") + relativedelta(months=1)).strftime("%Y-%m-%d")

            continue

        # If we get here...
        # This means that there are no monthly summaries for this i_date. We must be inside the month, or there are no conversations for the month. Check for weekly summaries for previous week starting previous monday.

        # Check for weekly summaries for the monday of this week:
        monday_of_week = get_monday_of_week(i_date)
        print_debug_line(f" -- The monday of the week is `monday_of_week`: {monday_of_week}.", "cyan")
        
        monday_of_end_date = get_monday_of_week(end_date)

        # If inside the week, skip. If outside the week, check for weekly summaries for the previous week.

        # Check for weekly summaries for this date.
        existing_weekly_summary = sql("SELECT * FROM groq_conversations LEFT JOIN groq_conv_types USING(conv_type_id) WHERE conv_type_id = 2 AND DATE(conv_first_msg) = %s;", (monday_of_week, ))

        if len(existing_weekly_summary) > 0 and i_date < monday_of_end_date:
            # If there is a weekly summary, we add it to the tapestry.
            print_debug_line(f" -- There is a weekly summary for the week of {monday_of_week}.", "cyan")
            str_weekly_summary = existing_weekly_summary[0]['conv_summary']

            lst_tapestry_ouput.append({
                "content": f"[{monday_of_week}] - Weekly memory:\n{str_weekly_summary}",
                "conv_id": existing_weekly_summary[0]['conv_id'],
                "conv_summary": existing_weekly_summary[0]['conv_summary'],
                "conv_type_name": existing_weekly_summary[0]['conv_type_name'],
                "conv_first_msg": existing_weekly_summary[0]['conv_first_msg'],
                "conv_last_msg": existing_weekly_summary[0]['conv_last_msg'],
                "conv_type_color": existing_weekly_summary[0]['conv_type_color'],
            })
                

            # Increment by one week.
            i_date = (datetime.strptime(monday_of_week, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")

            continue

        # This means that there are no weekly summaries for this week. We must be inside the week. Check for daily summaries for today.

        print_debug_line(f" -- `i_date` is: {i_date}.", "cyan")

        # Check for daily summaries for this date.
        existing_daily_summary = sql("SELECT * FROM groq_conversations LEFT JOIN groq_conv_types USING(conv_type_id) WHERE conv_type_id = 1 AND DATE(conv_first_msg) = %s;", (i_date, ))

        if len(existing_daily_summary) > 0 and i_date < end_date:
            # If there is a daily summary, we add it to the tapestry.
            print_debug_line(f" -- There is a daily summary for {i_date}.", "cyan")
            str_daily_summary = existing_daily_summary[0]['conv_summary']

            lst_tapestry_ouput.append({
                "content": f"[{i_date}] - Daily memory:\n{str_daily_summary}",
                "conv_id": existing_daily_summary[0]['conv_id'],
                "conv_summary": existing_daily_summary[0]['conv_summary'],
                "conv_type_name": existing_daily_summary[0]['conv_type_name'],
                "conv_first_msg": existing_daily_summary[0]['conv_first_msg'],
                "conv_last_msg": existing_daily_summary[0]['conv_last_msg'],
                "conv_type_color": existing_daily_summary[0]['conv_type_color'],
            })
                

            # Increment by one day.
            i_date = (datetime.strptime(i_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

            continue
        
        # If we get here, it means that there are no daily summaries for this day. We must be inside the day. Check for conversational summaries for today.

        # Check for conversational summaries for this date.
        sql_conv_summaries = sql("""SELECT * FROM groq_conversations LEFT JOIN groq_conv_types USING(conv_type_id) WHERE DATE(conv_first_msg) = %s""", (i_date, ))
        print_debug_line(f" -- The conversational summaries for `i_date`: {i_date} are `sql_conv_summaries`: {sql_conv_summaries}.", "cyan")

        if len(sql_conv_summaries) > 0 and i_date <= end_date:
            # If there are messages for today, we grab the conversational summary.
            print_debug_line(f" -- There are conversational summaries for {i_date}.", "cyan")

            for conv_summary in sql_conv_summaries:
                print_debug_line(f" -- The conversational summary for `conv_summary['conv_id']`: {conv_summary['conv_id']}.", "cyan")

                str_conversational_summary = conv_summary['conv_summary']

                lst_tapestry_ouput.append({
                    "content": f"[{i_date}] - Conversational memory:\n{str_conversational_summary}",
                    "conv_id": conv_summary['conv_id'],
                    "conv_summary": conv_summary['conv_summary'],
                    "conv_type_name": conv_summary['conv_type_name'],
                    "conv_first_msg": conv_summary['conv_first_msg'],
                    "conv_last_msg": conv_summary['conv_last_msg'],
                    "conv_type_color": conv_summary['conv_type_color'],
                })
                

            # Increment by one day.
            i_date = (datetime.strptime(i_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

            continue

        else:
            #pass
            # If we get here, we're at the end. We have no memories for this day. We increment by one day.
            i_date = (datetime.strptime(i_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

        # If we get here, we're at the end. We have no memories for this day. We increment by one day.

        # i_date = (datetime.strptime(i_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    print_debug_line(f" -- The tapestry output is `lst_tapestry_ouput`: {lst_tapestry_ouput}.", "green")

    # Debug message about success
    print_debug_line(f" -- The tapestry has been restored.", "green")

    return lst_tapestry_ouput



def prompt_for_weekly_summary():
    return "From the following daily summaries, createa a weekly summary. Write it as a first person POV memory of the assistant (Uni). Do not mention it's a summary / journal entry."

def prompt_for_daily_summary():
    return "From the following conversation, create a daily summary. Write it as a first person POV memory of the assistant (Uni). Do not mention it's a summary / journal entry."

def prompt_for_conversational_summary():
    return "From the following conversation, create a conversational summary / journal entry. Write it as a first person POV memory of the assistant (Uni). Do not mention it's a summary."

def call_api_for_level_summary(messages):

    print_debug_line(f" -- `messages` coming in{ messages }.", "cyan")

    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )
    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        # model="llama3-70b-8192",
        messages=messages
    )

    response = completion.choices[0].message
    print_debug_line(f" -- The response is `response`: {response}.", "white")
    # print_debug_line(f" -- The response content is `response.content`: {response.content}.", "white")
    
    # Wait 2 seconds before returning the response to not overload the API.
    time.sleep(2)

    return response.content


### Useful internal functions. ###

def get_start_date():
    start_date = sql("""SELECT DATE(MIN(msg_created)) AS start_date FROM groq_messages""")
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