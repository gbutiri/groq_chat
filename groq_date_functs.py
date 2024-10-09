import datetime
from datetime import datetime, timedelta
from groq_system_functs import print_debug_line
from pytz import timezone

def daterange(start_date, end_date):
    
    start_date_timestamp = datetime.strptime(str(start_date), '%Y-%m-%d %H:%M:%S')
    end_date_timestamp = datetime.strptime(str(end_date), '%Y-%m-%d %H:%M:%S')

    for n in range(int((end_date_timestamp - start_date_timestamp).days) + 1):
        yield start_date_timestamp + timedelta(n)

def date_range(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    delta = timedelta(days=1)
    current = start
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += delta
        # print_debug_line(f" -- The current date is `current`: {current}.", "green") 

def get_monday_of_week(date):
    date = datetime.strptime(str(date), "%Y-%m-%d")
    monday = date - timedelta(days=date.weekday())
    return str(monday.strftime("%Y-%m-%d"))


def get_first_of_month(date):
    date = datetime.strptime(str(date), "%Y-%m-%d")
    first_day = date.replace(day=1)
    return str(first_day.strftime("%Y-%m-%d"))


def get_first_monday_of_month(str_first_of_month):
    first_of_month = datetime.strptime(str_first_of_month, "%Y-%m-%d")
    first_monday = first_of_month - timedelta(days=first_of_month.weekday())
    return str(first_monday.strftime("%Y-%m-%d"))

def get_first_sunday_of_month(str_first_of_month):
    first_of_month = datetime.strptime(str_first_of_month, "%Y-%m-%d")
    first_sunday = first_of_month + timedelta(days=(6 - first_of_month.weekday()))
    return str(first_sunday.strftime("%Y-%m-%d"))