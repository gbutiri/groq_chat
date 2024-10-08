import datetime
from datetime import datetime, timedelta


def daterange(start_date, end_date):
    
    start_date_timestamp = datetime.strptime(str(start_date), '%Y-%m-%d %H:%M:%S')
    end_date_timestamp = datetime.strptime(str(end_date), '%Y-%m-%d %H:%M:%S')

    for n in range(int((end_date_timestamp - start_date_timestamp).days) + 1):
        yield start_date_timestamp + timedelta(n)
