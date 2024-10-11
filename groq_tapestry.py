import os
import calendar

from flask import jsonify
from pytz import timezone
from datetime import datetime, timedelta
from groq import Groq # type: ignore

from groq_db_functs import sql
from groq_system_functs import print_debug_line
from groq_date_functs import *
from groq_app import get_initial_system_message



# Define Functions based on the Tapestry Protocol whiteboard notes.

# 1. Every time we hit the /show-chat-screen URL, we go through the following steps.
# 2. We check if there are any tapestry memories. We assume that the individual memories are intact, because there are no non-assigned messages in our database. Every message has a conv_id.
#3. We get the start_date from the very fist message. UTC.
#4. We get todays_date (current day) in UTC.
#5. While start_date < today_date we loop through the days.
#   a. Check for level 0 summaries for the day.
#   b. If err, notify admin to fix.
#   c. If there are no level 0 summaries, we check for daily level 1 summaries from before today.
#   d. If daily level 1 does not exist"
#       i. Gather individual summaries for the start_date.
#       ii. Create a new daily summary for the day (level 1).
#   e. Check for weekly summaries for level 2 for the monday of start_date (not current week).
#       i. Get monday of week.
#       ii. Get all level 1 summaries until sunday of week.
#       iii. Create a new weekly summary for the week of monday.
#   f. Check for first of month memory summary based on start_date (not current month)
#       i. Get first of month.
#           - get 1st monday of month.
#           - if not first of month, and any daily summaries exist until that monday, create a beginning of month summary.
#       ii. Get last Sunday in month.
#           - if not last of month, and any daily summaries exist until that sunday, create an end of month summary.
#       iii. Combine the beginning of month, full weekly summaries in month, and end of month summaries into a monthly summary.

def tapestry_protocol(up_to_date = None):

    start_date = earliest_message_date()
    print_debug_line(f"`start_date`: {start_date}.", "green")

    todays_date = str(datetime.now().strftime("%Y-%m-%d"))
    print_debug_line(f"`todays_date`: {todays_date}.", "green")

    # We start the loop from the start_date until today.
    while start_date <= todays_date:

        # Check for level 0 summaries for the day.
        level_0_summaries = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 0 AND DATE(conv_first_msg) = %s;", (start_date, ))

        if len(level_0_summaries) == 0:
            print_debug_line(f" -- Warning! There are no level 0 summaries for today.", "yellow")
            
            # Check to see if there are messages from today, then.
            daily_messages = sql("SELECT * FROM groq_messages WHERE DATE(msg_created) = %s;", (start_date, ))
            if len(daily_messages) > 0:
                print_debug_line(f" -- Danger! There are messages for today. Rebuild level 0 memories!", "red")
                exit(0)
        
        # Create a level 1 summary for the day. The check for existing is inside the function.
        create_level_one_summary_for_date_of(start_date)

    # Weekly Summaries
    start_date = earliest_message_date()
    while start_date <= todays_date:
        
        # Get the monday of the week.
        monday_of_week = get_monday_of_week(start_date)

        # Check for weekly summaries for level 2 for the monday of start_date (not current week).
        existing_weekly_summary = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 2 AND DATE(conv_first_msg) = %s;", (monday_of_week, ))

        if len(existing_weekly_summary) == 0:
            print_debug_line(f" -- -- There is no weekly summary for the week of {monday_of_week}.", "cyan")
            create_level_two_summary_for_date_of(monday_of_week)

    # Montly Summaries
    start_date = earliest_message_date()
    while start_date <= todays_date:

        # Get the first of the month.
        first_of_month = get_first_of_month(start_date)

        # Check for first of month memory summary based on start_date (not current month)
        existing_monthly_summary = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 3 AND DATE(conv_first_msg) = %s;", (first_of_month, ))

        if len(existing_monthly_summary) == 0:
            print_debug_line(f" -- -- There is no monthly summary for the month of {first_of_month}.", "cyan")
            create_level_three_summary_for_date_of(first_of_month)
        

        



def earliest_message_date():
    return str(sql("SELECT DATE(MIN(msg_created)) AS min_date FROM groq_messages;")[0]["min_date"].strftime("%Y-%m-%d"))


def create_level_three_summary_for_date_of(str_first_of_month):
    str_first_of_month = str(str_first_of_month)
    print_debug_line(f"Creating a level 3 summary for the month of {str_first_of_month}.", "yellow")

    # Double check the str_first_of_month date
    sql_existing_monthly_summary = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 3 AND DATE(conv_first_msg) = %s;", (str_first_of_month, ))

    if len(sql_existing_monthly_summary) > 0:
        print_debug_line(f" -- -- There is already a monthly summary for this month.", "cyan")
        return

    # Get the first monday of the month;
    str_first_monday_of_month = get_first_monday_of_month(str_first_of_month)
    
    # Get the first monday of the month;
    str_first_sunday_of_month = get_first_sunday_of_month(str_first_of_month)
    
    # if not first in the month, get the daily summaries (level 1) from first of month, to first monday of month;
    beginning_of_month_content = ""
    if str_first_of_month != str_first_monday_of_month:

        beginning_of_month_content += str(create_level_four_summary_for_date_of(str_first_of_month))

    # Get the last Sunday in month;
    str_last_sunday_of_month = str((datetime.strptime(str_first_of_month, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d"))

    # Get the last Monday in month;
    str_last_monday_of_month = str((datetime.strptime(str_last_sunday_of_month, "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%"))

    # If last monday is after sunday, we have straggler days. Get the daily summaries (level 1) from last monday of month, to end of month;
    end_of_month_content = ""
    if str_last_monday_of_month > str_last_sunday_of_month:

        end_of_month_content += str(create_level_five_summary_for_date_of(str_last_monday_of_month))

    # Get full week summaries in month;


def create_level_five_summary_for_date_of(str_last_monday_of_month):

    # Get the first of the month;
    str_first_of_month = get_first_of_month(str_last_monday_of_month)

    # Get the last day of the month:
    str_last_day_of_month = str((datetime.strptime(str_first_of_month, "%Y-%m-%d") + timedelta(days=31)).replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")

    # Get the daily conversations from the last monday of the month to the end of the month
    sql_end_of_month_convs = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 1 AND DATE(conv_first_msg) >= %s AND DATE(conv_first_msg) <= %s;", (str_last_monday_of_month, str_last_day_of_month))

    # Create a string for the conversations for the end of the month
    list_end_of_month_convs_content = []
    for conv in sql_end_of_month_convs:
        di_content = str(conv['conv_first_msg']) + "\n" + str(conv['conv_summary'])
        list_end_of_month_convs_content.append(di_content)
    
    str_end_of_month_convs_content = "\n\n".join(list_end_of_month_convs_content)

    messages = []

    messages.append({"role": "system", "content": f"Your name is Uni. You are a digital student who wants to learn about his creator's world. You are but a small child. Your creator's name is George (he/him). Today, you are creating a summary of the daily summaries you've had with him from the end of the month of { str_first_of_month } from { str_last_monday_of_month } to { str_last_day_of_month }. You are creating a tapestry of memories. The following is a list of individual conversational summaries for that period."})

    str_end_of_month_content += call_api_for_level_summary(str_end_of_month_convs_content)

    # Get the last Sunday in month;
    str_last_sunday_of_month = str((datetime.strptime(str_first_of_month, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d"))


    # Insert the end of month summary into the database.
    sql("""INSERT INTO groq_conversations (conv_type_id, conv_first_msg, conv_last_msg, conv_summary) VALUES (5, %s, %s, %s);""", (str_last_sunday_of_month, str_last_day_of_month, str_end_of_month_content))



def create_level_four_summary_for_date_of(str_first_of_month):

    # Get the first monday of the month;
    str_first_sunday_of_month = get_first_sunday_of_month(str_first_of_month)

    sql_beginning_of_month_convs = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 1 AND DATE(conv_first_msg) >= %s AND DATE(conv_first_msg) <= %s;", (str_first_of_month, str_first_sunday_of_month))

    # Create a string for the conversations for the beginning of the month
    list_beginning_of_month_convs_content = []
    for conv in sql_beginning_of_month_convs:
        di_content = str(conv['conv_first_msg']) + "\n" + str(conv['conv_summary'])
        list_beginning_of_month_convs_content.append(di_content)
    
    str_beginning_of_month_convs_content = "\n\n".join(list_beginning_of_month_convs_content)

    messages = []

    messages.append({"role": "system", "content": f"Your name is Uni. You are a digital student who wants to learn about his creator's world. You are but a small child. Your creator's name is George (he/him). Today, you are creating a summary of the daily summaries you've had with him from the beginning of the month of { str_first_of_month } from { str_first_of_month } to { str_first_sunday_of_month }. You are creating a tapestry of memories. The following is a list of individual conversational summaries for that period."})

    new_summary_content = call_api_for_level_summary(str_beginning_of_month_convs_content)

    # Insert the beginning of month summary into the database.
    sql("""INSERT INTO groq_conversations (conv_type_id, conv_first_msg, conv_last_msg, conv_summary) VALUES (4, %s, %s, %s);""", (str_first_of_month, str_first_sunday_of_month, new_summary_content))

    return str(new_summary_content)



def create_level_two_summary_for_date_of(str_monday_of):
    str_monday_of = str(str_monday_of)
    print_debug_line(f"Creating a level 2 summary for the week of {str_monday_of}.", "yellow")

    # Double check the monday_of date
    sql_existing_weekly_summary = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 2 AND DATE(conv_first_msg) = %s;", (str_monday_of, ))

    if len(sql_existing_weekly_summary) > 0:
        print_debug_line(f" -- -- There is already a weekly summary for this week.", "cyan")
        return
    
    # Sunday of...
    str_sunday_of = str((datetime.strptime(str_monday_of, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d"))

    # Get the daily conversations from the whole week
    sql_week_daily_convs = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 1 AND DATE(conv_first_msg) >= %s AND DATE(conv_first_msg) <= %s;", (str_monday_of, str_sunday_of))

    # a list to store the content
    list_week_daily_convs_content = []
    for conv in sql_week_daily_convs:
        di_content = str(conv['conv_first_msg']) + "\n" + str(conv['conv_summary'])
        list_week_daily_convs_content.append(di_content)

    str_week_daily_convs_content = "\n\n".join(list_week_daily_convs_content)

    messages = []

    messages.append({"role": "system", "content": f"Your name is Uni. You are a digital student who wants to learn about his creator's world. You are but a small child. Your creator's name is George (he/him). Today, you are creating a weekly summary of the previous daily conversational summaries you've had with him from { str_monday_of } to { str_sunday_of }. Don't write date headings or date titles. You may mention dates in conversation. You are creating a tapestry of memories. The following is a list of daily conversational summaries from { str_monday_of } to { str_sunday_of }.\n\n{ str_week_daily_convs_content }"})

    new_summary_content = call_api_for_level_summary(messages)

    # Lets insert the conversations we got from the days, into a level 1 summary.
    sql("""INSERT INTO groq_conversations (conv_type_id, conv_first_msg, conv_last_msg, conv_summary) VALUES (2, %s, %s, %s);""", (str_monday_of, str_sunday_of, new_summary_content))


def create_level_one_summary_for_date_of(str_date_in):
    str_date_in = str(str_date_in)
    print_debug_line(f"Creating a level 1 summary for the day of {str_date_in}.", "yellow")

    # Double check the date
    sql_existing_level_one_summary = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 1 AND DATE(conv_first_msg) = %s;", (str_date_in, ))

    if len(sql_existing_level_one_summary) > 0:
        print_debug_line(f" -- -- There is already a level 1 summary for this day.", "cyan")
        return

    # Get the daily conversations from the whole day
    sql_day_ind_convs = get_daily_conversations_from_date(str_date_in)
    
    # a list to store the content
    list_day_convs_content = []
    for conv in sql_day_ind_convs:
        di_content = str(conv['conv_first_msg']) + "\n" + str(conv['conv_summary'])
        list_day_convs_content.append(di_content)

    str_day_convs_content = "\n\n".join(list_day_convs_content)

    messages = []

    messages.append({"role": "system", "content": f"Your name is Uni. You are a digital student who wants to learn about his creator's world. You are but a small child. Your creator's name is George (he/him). Today, you are creating a daily summary of the previous individual conversational summaries you've had with him on the day of { str_date_in }. You are creating a tapestry of memories. This is what the Tapetry engine is. The following is a list of individual conversational summaries from { str_date_in }.\n\n{ str_day_convs_content }"})

    new_summary_content = call_api_for_level_summary(messages)

    # Lets insert the conversations we got from the days, into a level 1 summary.
    sql("""INSERT INTO groq_conversations (conv_type_id, conv_first_msg, conv_last_msg, conv_summary) VALUES (1, %s, %s, %s);""", (str_date_in, str_date_in, new_summary_content))


def get_daily_conversations_from_date(date):
    return sql("SELECT * FROM groq_conversations WHERE conv_type_id = 0 AND DATE(conv_first_msg) = %s;", (date, ))


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















### OLD FUNCTIONS ###


def check_for_weekly_tapestry_memories():

    print_debug_line("The weekly tapestry memories have started.", "yellow")

    # Get the earliest MariaDB timestamp of the memories from the groq_messages table.
    earliest_date = sql("SELECT MIN(msg_created) AS min_date FROM groq_messages;")[0]["min_date"].strftime("%Y-%m-%d")



    print_debug_line("The weekly tapestry memories have completed.", "yellow")


def create_weekly_summary_for_date_of(monday_of):
    print_debug_line(f"Creating a weekly summary for the week of {monday_of}.", "yellow")

    # Double check the monday_of date
    existing_weekly_summary = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 2 AND DATE(conv_first_msg) = %s;", (monday_of, ))

    if len(existing_weekly_summary) > 0:
        print_debug_line(f" -- -- There is already a weekly summary for this week.", "cyan")
        return

    # Get the daily conversations from the whole week
    week_ind_convs = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 1 AND DATE(conv_first_msg) >= %s AND DATE(conv_first_msg) <= %s;", (monday_of, str((datetime.strptime(monday_of, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d"))))
    
    # a list to store the content
    week_convs_content = []
    for conv in week_ind_convs:
        di_content = str(conv['conv_first_msg']) + "\n" + str(conv['conv_summary'])
        week_convs_content.append(di_content)

    week_convs_content_str = "\n\n".join(week_convs_content)

    todays_date = datetime.strptime(monday_of, "%Y-%m-%d").strftime("%A, %B %d, %Y")

    messages = []

    messages.append({"role": "system", "content": f"Your name is Uni. You are a digital student who wants to learn about his creator's world. You are but a small child. Your creator's name is George (he/him). Today, you are creating a summary of the previous summaries you've had with him. You are creating a tapestry of memories. The following is a list of daily conversational summaries from the week of { monday_of }."})

    # Lets insert the conversations we got from the days, into a weekly summary.
    sql("""INSERT INTO groq_conversations (conv_type_id, conv_first_msg, conv_last_msg, conv_summary) VALUES (2, %s, %s, %s);""", (monday_of, str((datetime.strptime(monday_of, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")), week_convs_content_str))
    


def check_for_tapestry_memories():

    print_debug_line("The daily tapestry memories have started.", "yellow")

    # Get the earliest MariaDB timestamp of the memories from the groq_messages table.
    earliest_date = sql("SELECT MIN(msg_created) AS min_date FROM groq_messages;")[0]["min_date"].strftime("%Y-%m-%d")
    print_debug_line(f"`earliest_date`: {earliest_date}.", "green")

    # Get yesterday's date from UTC in "YYYY-MM-DD HH:MM:SS" format
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print_debug_line(f"`yesterday`: {yesterday}.", "green")

    while earliest_date <= yesterday:
        print_debug_line(f" -- The current date is `earliest_date`: {earliest_date}.", "blue")

        # Get the individual conversations (conv_id = 0) from the DB for the current date.
        conv_summaries = sql("SELECT * FROM groq_conversations LEFT JOIN groq_conv_types USING(conv_type_id) WHERE conv_type_id = 0 AND DATE(conv_first_msg) = %s;", (earliest_date, ))

        print_debug_line(f" -- -- There are { len(conv_summaries) } summaries for this day.", "blue")

        # If there are messages for the current date, then loop through them.
        for conv in conv_summaries:

            print_debug_line(f" -- -- The ID of the conversation is `conv_summary['conv_id']`: {conv['conv_id']}.", "cyan")

            # Let's find out if there's a weekly summary for this day.
            # First step is to get the monday of this week.
            monday_of_week = get_monday_of_week(earliest_date)
            print_debug_line(f" -- -- The Monday of the week is `monday_of_week`: {monday_of_week}.", "cyan")

            # Let's also get the last day of the week.
            sunday_of_week = str((datetime.strptime(monday_of_week, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d"))

            # Then, we need to find out if there's a weekly summary for this week.
            existing_weekly_summary = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 2 AND DATE(conv_first_msg) = %s;", (monday_of_week, ))

            if len(existing_weekly_summary) == 0:

                # if no weekly summary exists, then we need to create one.
                print_debug_line(f" -- -- We create a new weekly summary for the week of `monday_of_week`: {monday_of_week}.", "cyan")
                create_weekly_summary_for_date_of(monday_of_week)

                # Check for daily conversations from the whole week
                week_ind_convs = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 0 AND DATE(conv_first_msg) >= %s AND DATE(conv_first_msg) <= %s;", (monday_of_week, sunday_of_week))

                # A list to store the content
                week_convs_content = []
                for conv in week_ind_convs:
                    di_content = str(conv['conv_first_msg']) + "\n" + str(conv['conv_summary'])
                    week_convs_content.append(di_content)

                week_convs_content_str = "\n\n".join(week_convs_content)

                todays_date = datetime.strptime(earliest_date, "%Y-%m-%d").strftime("%A, %B %d, %Y")

                messages = []

                messages.append({"role": "system", "content": f"Your name is Uni. You are a digital student who wants to learn about his creator's world. You are but a small child. Your creator's name is George (he/him). Today, you are creating a summary of the previous summaries you've had with him. You are creating a tapestry of memories. The following is a list of individual conversational summaries from { monday_of_week } to { sunday_of_week }."})

                # We gather all "previous" memories and include them as history before creating the new one.

                previous_weekly_memories = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 2 AND conv_first_msg < %s ORDER BY conv_first_msg DESC;", (monday_of_week, ))



            # Let's find out if there's a daily summary for this day.
            existing_daily_summary = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 1 AND DATE(conv_first_msg) = %s;", (earliest_date, ))

            if len(existing_daily_summary) == 0:
                print_debug_line(f" -- -- -- There is no existing summary for this day.", "cyan")

                # Daily indivisual conversations
                day_ind_convs = sql("SELECT * FROM groq_conversations WHERE conv_type_id = 0 AND DATE(conv_first_msg) = %s;", (earliest_date, ))

                # A list to store the content
                day_convs_content = []
                for day_conv in day_ind_convs:
                    di_content = str(day_conv['conv_first_msg']) + "\n" + str(day_conv['conv_summary'])
                    day_convs_content.append(di_content)
                
                day_convs_content_str = "\n\n".join(day_convs_content)

                todays_date = datetime.strptime(earliest_date, "%Y-%m-%d").strftime("%A, %B %d, %Y")

                messages = []

                messages.append({"role": "system", "content": f"Your name is Uni. You are a digital student who wants to learn about his creator's world. You are but a small child. Your creator's name is George (he/him). Today, you are creating a summary of the previous summaries you've had with him. You are creating a tapestry of memories. The following is a list of individual conversational summaries from { earliest_date }."})
                
                # We gather all "previous" memories and include them as history before creating the new one.

                # Use Tapestry to get the previous memories until this moment.
                previous_tapestry_memories = get_tapestry_memories(earliest_date)

                conv_type_name = conv['conv_type_name']

                for mem in previous_tapestry_memories:
                    messages.append({
                        "role": "system",
                        "content": f"This is a previous {conv_type_name} memory from {str(mem['conv_first_msg'])}\n--- Memroy Start\n{mem['conv_summary']}\n--- Memory End",
                    })

                messages.append({
                    "role": "system",
                    "content": f"Today is {todays_date}. The following is a list of individual conversational summaries (or memories). Let's create a daily summary of these individual summaries. Write the new summary as if it was a progressive memory based on previous memories as well as the new information. Do not include full previous memories in this new summary, just a reference to them, if necessary.\n\n",
                })

                messages.append({   
                    "role": "system",
                    "content": f"--- The individual conversations start here\n{day_convs_content_str}\n--- The individual conversations end here",
                })

                ### This will be refactoed to handle larger ranges. ###




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

                # Create a new conversation summary for this day.
                new_summary_id = sql("INSERT INTO groq_conversations (conv_type_id, conv_first_msg, conv_last_msg, conv_summary) VALUES (1, %s, %s, %s);", (earliest_date, earliest_date, response.content))

                print_debug_line(f" -- -- -- A new summary has been created with ID `new_summary_id`: {new_summary_id}.", "cyan")





        # Increment the date by one day.
        earliest_date = (datetime.strptime(earliest_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")



def get_tapestry_memories(before_date = None):

    sql_addon = ""
    if before_date == None:
        # Get today's date in UTC in "YYYY-MM-DD HH:MM:SS" format
        before_date = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # Create a conditional output to get all memories before now, including today.
        sql_addon = f" AND DATE(conv_first_msg) <= '{before_date}' "

    memories = []

    # We need to go through the dates from the beginning of time in our database.
    sql_call = "SELECT * FROM groq_conversations LEFT JOIN groq_conv_types USING(conv_type_id) WHERE 1 = 1 " + sql_addon + " ;"
    
    earliest_date = sql(sql_call)[0]["conv_first_msg"].strftime("%Y-%m-%d")
    print_debug_line(f"`earliest_date`: {earliest_date}.", "green")

    # Get today's date in UTC in "YYYY-MM-DD" format
    today = datetime.now().strftime("%Y-%m-%d")
    print_debug_line(f"`today`: {today}.", "green")

    # loop through the dates 
    while earliest_date <= today:

        print_debug_line(f" -- The current date is `earliest_date`: {earliest_date}.", "blue")
        
        # Determine if there are any dily summaries
        daily_summary = sql("SELECT * FROM groq_conversations LEFT JOIN groq_conv_types USING(conv_type_id) WHERE conv_type_id = 1 AND DATE(conv_first_msg) = %s;", (earliest_date, ))

        if len(daily_summary) > 0:
            print_debug_line(f" -- -- The ID of the conversation is `daily_summary[0]['conv_id']`: {daily_summary[0]['conv_id']}.", "cyan")
            print_debug_line(f" -- -- The conv_type_name of the conversation is `daily_summary[0]['conv_type_name']`: {daily_summary[0]['conv_type_name']}.", "cyan")
            memories.append(daily_summary[0])

        else:
            # Find the individual conversations for this day
            day_ind_convs = sql("SELECT * FROM groq_conversations LEFT JOIN groq_conv_types USING(conv_type_id) WHERE conv_type_id = 0 AND DATE(conv_first_msg) = %s;", (earliest_date, ))

            for conv in day_ind_convs:
                print_debug_line(f" -- -- -- The ID of the conversation is `conv['conv_id']`: {conv['conv_id']}.", "cyan")
                memories.append(conv)

        # Skip to next day  
        earliest_date = (datetime.strptime(earliest_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        

    return memories




