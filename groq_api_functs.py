import requests
import os
from datetime import datetime
import pytz
from flask import jsonify


def tell_time():
    try:
        # Hardcoded timezone for Cleveland, OH
        timezone = "America/New_York"
        time_response = requests.get(f'https://worldtimeapi.org/api/timezone/{timezone}')
        time_data = time_response.json()
        # convert the data into a human readable format
        # First, we do the time and date format : .strftime('%a, %b %d, \'%y, %I:%M %p').replace(' 0', ' ').replace('AM', 'am').replace('PM', 'pm')
        time_and_date_string = str(time_data.get('datetime'))
        time_and_date_formatted = datetime.strptime(time_and_date_string, '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(pytz.timezone(timezone)).strftime('%a, %b %d, \'%y, %I:%M %p').replace(' 0', ' ').replace('AM', 'am').replace('PM', 'pm')

        return f"The current time and date in Cleveland, OH is {time_and_date_formatted}."
    
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
        weather_data = {
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
        }

        # Let's return back the weather in human readable format.
        return f"The current weather condition for {location} are as follows. {weather_data['condition']} with a temperature of {weather_data['temperature_f']}°F ({weather_data['temperature_c']}°C). The humidity is {weather_data['humidity']}%. The wind speed is {weather_data['wind_mph']} mph ({weather_data['wind_kph']} kph)."

    except Exception as e:
        return jsonify({'error': str(e)}), 500


