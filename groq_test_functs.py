from flask import jsonify


def testing_uni(number_in):
    half_of_number = int(number_in) / 2
    return jsonify({"secret": f"Hello Uni! It's me, George, from inside the function. If the function works, you should get back an integer representing approximately 1/2 of the original value {half_of_number}."})


