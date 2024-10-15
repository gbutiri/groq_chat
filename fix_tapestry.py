from flask import Flask, jsonify, request, render_template, render_template_string
import os

from groq import Groq # type: ignore
import json

from groq_db_functs import *
from groq_system_functs import *
from groq_date_functs import *
from datetime import datetime, timedelta


app = Flask(__name__)

# Documentation
# Level 0 conv_id = conversational summary
# Level 1 conv_id = daily summary
# Level 2 conv_id = weekly summary
# Level 3 conv_id = monthly summary
# Level 4 conv_id = beginning of month summary
# Level 5 conv_id = end of month summary
# Level 6 conv_id = quarter summary
# Level 7 conv_id = yearly summary

# DB Structure
"""
CREATE TABLE `groq_conversations` (
  `conv_id` BIGINT(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `conv_type_id` INT(11) NOT NULL DEFAULT 0,
  `conv_summary` TEXT NOT NULL,
  `conv_first_msg` DATETIME DEFAULT NULL,
  `conv_last_msg` DATETIME DEFAULT NULL,
  `conv_created` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  `conv_updated` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP() ON UPDATE CURRENT_TIMESTAMP(),
  PRIMARY KEY (`conv_id`)
)

CREATE TABLE `groq_messages` (
  `msg_id` BIGINT(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `conv_id` BIGINT(20) UNSIGNED NOT NULL DEFAULT 0,
  `msg_role` VARCHAR(32) NOT NULL,
  `msg_content` TEXT NOT NULL,
  `msg_tool_name` VARCHAR(255) NOT NULL DEFAULT '',
  `msg_tool_id` VARCHAR(255) NOT NULL DEFAULT '',
  `msg_f_name` VARCHAR(255) NOT NULL DEFAULT '',
  `msg_created` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  `msg_updated` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP() ON UPDATE CURRENT_TIMESTAMP(),
  PRIMARY KEY (`msg_id`)
)

CREATE TABLE `groq_conv_types` (
  `conv_type_id` INT(11) UNSIGNED NOT NULL DEFAULT 0,
  `conv_type_name` VARCHAR(20) NOT NULL DEFAULT '',
  `conv_type_color` VARCHAR(10) NOT NULL DEFAULT '',
  PRIMARY KEY (`conv_type_id`)
)
"""



def get_earliest_date():
    sql_earliest_date = sql("""SELECT MIN(DATE(msg_created)) AS `min_msg_created` FROM groq_messages""")
    if sql_earliest_date:
        earliest_date = sql_earliest_date[0]["min_msg_created"]

    return str(earliest_date)


@app.route('/fix-tapestry', methods=['GET'])
def fix_tapestry():
    
    print_debug_line("START --------------", "red")

    # Get the earliest message memory date
    earliest_date = get_earliest_date()
    print_debug_line(f"Earliest date: {earliest_date}", "yellow")

    # Get the current date
    todays_date = get_todays_date()
    print_debug_line(f"Current date: {todays_date}", "yellow")

    # Create an iterator for the earliest date
    i_date = earliest_date

    # Create a while loop to today's date
    print_debug_line("Looping through dates", "cyan")
    while i_date < todays_date:
        print_debug_line(f"-- Earliest date: {earliest_date}", "yellow")
        print_debug_line(f"-- Current date: {todays_date}", "yellow")
        print_debug_line(f"-- i_date: {i_date}", "yellow")

        # First thing we do is check is if we have a daily summary for today. The dates go incrementally.
        sql_existing_daily_summary = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 1;""", (i_date,))
        if sql_existing_daily_summary:
            print_debug_line(f"-- Daily summary for {i_date} already exists", "blue")
            i_date = (datetime.strptime(i_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

            # Need to check if the i_date is before this current week. If it is, we need to check for a weekly summary. If it doesn't exist, we need to create it.

            i_week = get_week_of_date(i_date)
            current_week = get_current_week_start()
            print_debug_line(f"-- i_week: {i_week}", "yellow")
            print_debug_line(f"-- current_week: {current_week}", "yellow")

            if i_week:
                print_debug_line(f"-- Weekly summary for {i_date} already exists", "blue")
                i_month = get_month_of_date(i_date)

                if i_month:
                    print_debug_line(f"-- Monthly summary for {i_date} already exists", "blue")

            else:
                print_debug_line(f"-- Weekly summary for {i_date} does not exist", "red")
                create_weekly_summary(i_date)
            
        else:
            print_debug_line(f"-- Daily summary for {i_date} does not exist", "red")
            if create_daily_summary(i_date):
                print_debug_line(f"-- Daily summary for {i_date} created", "green")
            else:
                print_debug_line(f"-- Daily summary for {i_date} not created", "yyellow")


        # Increment the earliest date
        i_date = (datetime.strptime(i_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    print_debug_line("STOP ---------------", "red")
    return jsonify({"status": "success"})


def get_week_start(i_date):
    # Get the week start date
    week_start = (datetime.strptime(i_date, "%Y-%m-%d") - timedelta(days=datetime.strptime(i_date, "%Y-%m-%d").weekday())).strftime("%Y-%m-%d")
    return str(week_start)

def get_week_end(i_date):
    # Get the week end date
    week_end = (datetime.strptime(i_date, "%Y-%m-%d") + timedelta(days=6 - datetime.strptime(i_date, "%Y-%m-%d").weekday())).strftime("%Y-%m-%d")
    return str(week_end)

def get_current_week_start():
    # Get the current week
    current_week = get_week_start(get_todays_date())
    return current_week


def get_month_of_date(i_date):
    # Get the month of the date
    month = i_date[:7]
    return month


def get_current_month_start():
    # Get the current month
    current_month = get_month_of_date(get_todays_date())
    return current_month    

def get_week_of_date(i_date):
    # Get the week of the date
    week_start = get_week_start(i_date)
    return str(week_start)

def create_daily_summary(i_date):

    # First, we check to see if we have messages.
    existing_messages = sql("""SELECT * FROM groq_messages WHERE DATE(msg_created) = %s;""", (i_date,))

    # If we do, we check to see if there are conversational summaries for the messages.
    if existing_messages:
        print_debug_line(f"-- Messages for {i_date} exist", "blue")
        existing_conversations = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 0;""", (i_date,))

        if existing_conversations:
            print_debug_line(f"-- Conversational summaries for {i_date} exist", "blue")
            # Create a daily summary for the day.

            generte_daily_summary(i_date)

        else:
            print_debug_line(f"-- Conversational summaries for {i_date} do not exist", "red")
            # Group messages by conv_id.
            
            # First, get the unique conv_ids from the messages.
            conv_ids = []
            for msg in existing_messages:
                if msg["conv_id"] not in conv_ids:
                    conv_ids.append(msg["conv_id"])
            
            # Next, create a conversational summary for each group.
            for conv_id in conv_ids:
                new_conv_id = create_conversational_summary(conv_id)

            # Get the created conversational summaries for the day:
            existing_conversations = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 0;""", (i_date,))
            if existing_conversations:
                print_debug_line(f"-- Conversational summaries for {i_date} exist", "blue")
                # Create a daily summary for the day.
                generte_daily_summary(i_date)

            # Create a daily summary for the day.

    else:
        print_debug_line(f"-- Messages for {i_date} do not exist", "red")
        return False



def get_tapestry(before_date = None):

    if before_date == None:
        before_date = get_todays_date()
    
    # The idea is to get the memories from the tapestry in the proper structure.

    # We have to check if any messages exist before the before_date.
    # Get the first date of the messages.
    start_date = get_earliest_date()
    print_debug_line(f"Start date: {start_date}", "yellow")

    # Create a while loop between the start_date and before_date
    i_date = start_date
    
    while i_date < before_date:
        print_debug_line(f"i_date: {i_date}", "yellow")

        # is i_date in current month?
        i_month = get_month_of_date(i_date)
        current_month = get_current_month_start()
        print_debug_line(f"i_month: {i_month}", "yellow")
        print_debug_line(f"current_month: {current_month}", "yellow")

        if i_month < current_month:
            # See if the monthly summary exists
            sql_existing_monthly_summary = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 3;""", (i_month,))
            
            if sql_existing_monthly_summary:
                print_debug_line(f"Monthly summary for {i_month} already exists", "blue")
                return sql_existing_monthly_summary[0]["conv_summary"]
            else:
                # Stop code and tell user.
                print_debug_line(f"Monthly summary for {i_month} does not exist", "red")
                exit()

        else:

            i_week = get_week_of_date(i_date)
            current_week = get_current_week_start()

            print_debug_line(f"i_week: {i_week}", "yellow")

            if i_week < current_week:

                # See if the weekly summary exists
                sql_existing_weekly_summary = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 2;""", (i_week,))
                
                if sql_existing_weekly_summary:
                    print_debug_line(f"Weekly summary for {i_week} already exists", "blue")
                    return sql_existing_monthly_summary[0]["conv_summary"]
                else:
                    # Stop code and tell user.
                    print_debug_line(f"Weekly summary for {i_week} does not exist", "red")
                    exit()
        
        # Increment the date
        i_date = (datetime.strptime(i_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")



def create_conversational_summary(conv_id = 0):
    
    # 1. Grab memories from tapestry:
    memories = get_tapestry()

    messages = []

    # 1a. Add memories to messages as an initial system message.

    for memory in memories:
        messages.append({
            "role":"system", 
            "content":memory
        })

    # 2. Get messages from database for conv_id
    sql_messages = sql("""SELECT * FROM groq_messages WHERE conv_id = %s;""", (conv_id,))
    if sql_messages:
        for msg in sql_messages:
            if msg["msg_role"] not in ["system", "tool"]:
                messages.append({
                    "role":msg["msg_role"], 
                    "content":str(msg["msg_created"]) + "\n" + msg["msg_content"]
                })
    
    # 3. Prompt for conversational summary:
    messages.append({
        "role":"system", 
        "content":"Summarize the following conversation into a concise paragraph. Focus only on key topics discussed, decisions made, and any important follow-ups. Exclude small talk or unrelated information. Keep the summary under 200 tokens."
    })

    # 4. Call the API
    response = call_the_api(messages)

    # 5. Save the conversational summary to the database
    # Make sure to replace into.
    if conv_id == 0:
        
        new_conv_id = sql("""INSERT INTO groq_conversations SET conv_type_id = %s, conv_summary = %s, conv_first_msg = %s, conv_last_msg = %s;""", (0, response, sql_messages[0]["msg_created"], sql_messages[-1]["msg_created"]))

        # 5a. Update the messages with the new conv_id
        sql("""UPDATE groq_messages SET conv_id = %s WHERE conv_id = %s;""", (new_conv_id, 0))

    else:

        # 5b. Update the conversational summary

        sql("""REPLACE INTO groq_conversations SET conv_id = %s, conv_type_id = %s, conv_summary = %s, conv_first_msg = %s, conv_last_msg = %s;""", (conv_id, 0, response, sql_messages[0]["msg_created"], sql_messages[-1]["msg_created"]))
        new_conv_id = conv_id
    
    return new_conv_id


def generte_daily_summary(i_date):

    # 1. Grab memories from tapestry:
    memories = get_tapestry()

    messages = []

    # 1a. Add memories to messages as an initial system message.

    for memory in memories:
        messages.append({
            "role":"system", 
            "content":memory
        })

    # Get the conversational summaries from i_date
    sql_conv_summaries = sql("""SELECT * FROM groq_conversations WHERE DATE(conv_first_msg) = %s AND conv_type_id = 0;""", (i_date,))
    
    if sql_conv_summaries:
        print_debug_line(f"-- Conversational summaries for {i_date} exist", "blue")
        # Create a daily summary for the day.
        

        for conv in sql_conv_summaries:
            messages.append({
                "role":"system", 
                "content": str(conv['conv_first_msg']) + "\n" + conv["conv_summary"]
            })

        # 3. Prompt for daily summary:
        messages.append({
            "role":"system", 
            "content":"Summarize the following conversational summaries into a cohesive daily summary. Focus on recurring themes, key decisions made, and any significant progress or unresolved tasks. Keep the summary concise and under 200 tokens.."
        })

        # 4. Call the API
        response = call_the_api(messages)

        # 5. Save the daily summary to the database
        # Make sure to replace into.
        new_conv_id = sql("""REPLACE INTO groq_conversations SET conv_type_id = %s, conv_summary = %s, conv_first_msg = %s, conv_last_msg = %s;""", (1, response, sql_conv_summaries[0]["conv_first_msg"], sql_conv_summaries[-1]["conv_last_msg"]))

    else:
        print_debug_line(f"-- Conversational summaries for {i_date} do not exist", "red")
        return False

    
def create_weekly_summary(i_date):
    pass


def call_the_api(messages):
    # In this we call the API.
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