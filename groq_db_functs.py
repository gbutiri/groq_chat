import mysql.connector


# Database connection configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'chat_api'
}


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